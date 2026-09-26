"""The commerce HTTP surface: catalogue, checkout, account and webhooks.

The surface is JSON only. No handler here renders markup and no response body
carries a candidate's origin: a buyer sees a preview served from our own host,
never the URL a good was found at. The publication gate already decided what may
be listed before any of this ran; this module is transport, not the decision.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, SecretStr

from packages.core.src.errors import VelmorError
from packages.services.src.auth.service import AccountService
from packages.services.src.commerce.catalogue_service import StorefrontCatalogue
from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.disclosure import SellerDisclosureCheck
from packages.services.src.commerce.errors import (
    CheckoutRefusedError,
    DeliveryRefusedError,
    GrantRefusedError,
    PreviewCoverMissingError,
    PreviewDigestMismatchError,
    PreviewNotFoundError,
    PreviewNotRenderableError,
    PreviewOriginUnreachableError,
)
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.commerce.preview import GoodPreview
from packages.services.src.domain.account import Account
from packages.services.src.domain.cart import Cart, CartLine
from packages.services.src.domain.catalogue_card import CatalogueCard, CategorySummary
from packages.services.src.domain.catalogue_query import CatalogueSort
from packages.services.src.domain.entitlement import Entitlement, EntitlementState
from packages.services.src.domain.presentation import DEFAULT_LOCALE, Locale
from packages.services.src.domain.seller import SellerDisclosure
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.errors import (
    PaymentNotificationError,
    PaymentProviderError,
)
from packages.services.src.payments.stripe_provider import StripeProvider
from packages.services.src.payments.stub_provider import StubPaymentProvider
from packages.services.src.persistence.contract import (
    EntitlementRepository,
    OrderRepository,
    SellerDisclosureRepository,
)

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


class CheckoutLineBody(BaseModel):
    """One cart line posted by the client; there is no server-side cart table."""

    model_config = {'frozen': True}

    candidate_id: str
    unit_amount: Decimal
    quantity: int


class CheckoutStartBody(BaseModel):
    """Checkout start payload: cart lines travel with the request (task 5.5 R5)."""

    model_config = {'frozen': True}

    provider_id: str
    return_url: str
    currency: str
    lines: tuple[CheckoutLineBody, ...]


class RefundBody(BaseModel):
    model_config = {'frozen': True}

    reason: str


class RegisterBody(BaseModel):
    """Credentials a buyer registers with. The password is never echoed back."""

    model_config = {'frozen': True}

    email: str
    password: str
    display_name: str


class SignInBody(BaseModel):
    model_config = {'frozen': True}

    email: str
    password: str


class ChangePasswordBody(BaseModel):
    model_config = {'frozen': True}

    current_password: str
    new_password: str


class UnauthenticatedError(VelmorError):
    """A guarded route was reached without a valid session.

    Raised by ``ApiApplication._require_buyer`` and turned into the fixed
    ``unauthenticated`` refusal by ``_unauthenticated_handler``. It is a value
    level refusal like every other in this module: no route catches it, and no
    route falls back to an identity taken from the request.
    """


class ApiApplication:
    """The HTTP surface of the platform.

    Routes are registered as bound methods rather than decorated module-level
    functions, so the handlers can read the injected services without a global.
    """

    SERVICE_NAME = 'velmor-api'
    OPERATOR_HEADER = 'x-operator-key'
    STRIPE_SIGNATURE_HEADER = 'stripe-signature'
    BEPAID_SIGNATURE_HEADER = 'content-signature'
    STUB_SIGNATURE_HEADER = 'x-stub-signature'
    AUTHORIZATION_HEADER = 'authorization'
    PREVIEW_CACHE_CONTROL = 'public, max-age=31536000, immutable'
    CORS_ALLOW_METHODS = ('GET', 'POST', 'OPTIONS')
    CORS_ALLOW_HEADERS = (
        'Content-Type',
        'Authorization',
        'X-Stub-Signature',
    )
    DEV_STOREFRONT_ORIGINS = (
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    )
    BASE_PROVIDER_IDS = ('stripe', 'bepaid')
    #: The ``unauthenticated`` refusal, which belongs to the transport rather
    #: than to ``AccountService``: a session problem is not an account outcome.
    UNAUTHENTICATED = 'unauthenticated'
    UNAUTHENTICATED_DETAIL = 'a valid session is required'
    #: Every account refusal, its fixed English detail and its status. ``reason``
    #: is the contract the storefront switches on; ``detail`` is for logs and
    #: developers and is never rendered to a buyer, so no password value and no
    #: internal identifier appears in either. A code with no entry raises a
    #: ``KeyError`` rather than inventing a response.
    REFUSAL_DETAILS: dict[str, str] = {
        AccountService.EMAIL_REQUIRED: 'an email address is required',
        AccountService.EMAIL_UNAVAILABLE: 'that email address cannot be used',
        AccountService.INVALID_CREDENTIALS: (
            'the email address and password did not match'
        ),
        AccountService.PASSWORD_TOO_SHORT: (
            'the password is shorter than the minimum length'
        ),
        AccountService.CURRENT_PASSWORD_INCORRECT: 'the current password is incorrect',
        AccountService.RATE_LIMITED: 'too many sign-in attempts; try again later',
    }
    REFUSAL_STATUSES: dict[str, int] = {
        AccountService.EMAIL_REQUIRED: 400,
        AccountService.EMAIL_UNAVAILABLE: 400,
        AccountService.INVALID_CREDENTIALS: 401,
        AccountService.PASSWORD_TOO_SHORT: 400,
        AccountService.CURRENT_PASSWORD_INCORRECT: 400,
        AccountService.RATE_LIMITED: 429,
    }
    #: The documented preview refusals and the status each maps to
    #: (openspec/specs/commerce/storefront; contract.md, GET
    #: /catalogue/goods/{candidate_id}/preview). 404 keeps one meaning - no
    #: saleable good here: unknown, withdrawn or not PAID_OK - and a preview that
    #: could not be produced is 502, whether the origin was unreachable or served
    #: a payload the platform cannot render. Two 502 causes sharing one status is
    #: deliberate: the operator's separating signal is the publication refusal
    #: reason, and no response body may describe the origin's bytes. A cover whose
    #: bytes are gone is 500: we wrote that row and the bytes went missing from our
    #: own cache, so the fault is our inconsistent state and not an upstream one,
    #: and 502 would send an operator to inspect an origin that is fine. It stays
    #: registered rather than falling through to the default handler so the body is
    #: fixed and names no origin. Re-running "velmor cover" repairs it.
    PREVIEW_REFUSALS: dict[type[VelmorError], tuple[int, str]] = {
        PreviewNotFoundError: (404, 'no preview exists for this good'),
        PreviewDigestMismatchError: (
            409,
            'the file no longer matches the recorded digest',
        ),
        PreviewOriginUnreachableError: (502, 'the preview could not be produced'),
        PreviewNotRenderableError: (502, 'the preview could not be produced'),
        PreviewCoverMissingError: (500, 'the preview could not be produced'),
    }

    def __init__(
        self,
        environment: str,
        catalogue: StorefrontCatalogue,
        preview: GoodPreview,
        grants: DeliveryGrantService,
        delivery: DeliveryService,
        entitlements: EntitlementRepository,
        clock: Callable[[], datetime],
        checkout: CheckoutService,
        disclosures: SellerDisclosureRepository,
        stripe: StripeProvider,
        bepaid: BePaidProvider,
        orders: OrderRepository,
        operator_refund_key: SecretStr,
        storefront_domain: str,
        accounts: AccountService,
        session_cookie_name: str,
        session_lifetime_seconds: int,
        password_min_length: int,
        stub: StubPaymentProvider | None = None,
        lifespan: Lifespan | None = None,
    ) -> None:
        self._environment = environment
        self._catalogue = catalogue
        self._preview = preview
        self._grants = grants
        self._delivery = delivery
        self._entitlements = entitlements
        self._clock = clock
        self._checkout = checkout
        self._disclosures = disclosures
        self._disclosure_check = SellerDisclosureCheck()
        self._stripe = stripe
        self._bepaid = bepaid
        self._stub = stub
        self._orders = orders
        self._operator_refund_key = operator_refund_key
        self._storefront_domain = storefront_domain
        self._accounts = accounts
        self._session_cookie_name = session_cookie_name
        self._session_lifetime_seconds = session_lifetime_seconds
        self._password_min_length = password_min_length
        self._lifespan = lifespan

    def build(self) -> FastAPI:
        app = FastAPI(
            title=self.SERVICE_NAME,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
            lifespan=self._lifespan,
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self._cors_origins(),
            allow_credentials=False,
            allow_methods=list(self.CORS_ALLOW_METHODS),
            allow_headers=list(self.CORS_ALLOW_HEADERS),
        )
        app.add_api_route('/health', self._health, methods=['GET'])
        for preview_error, refusal in self.PREVIEW_REFUSALS.items():
            app.add_exception_handler(preview_error, self._refusal_handler(*refusal))
        app.add_exception_handler(UnauthenticatedError, self._unauthenticated_handler)
        app.add_api_route('/', self._root, methods=['GET'])
        app.add_api_route(
            '/catalogue/categories', self._list_categories, methods=['GET']
        )
        app.add_api_route(
            '/catalogue/categories/{slug}', self._get_category, methods=['GET']
        )
        app.add_api_route('/catalogue/goods', self._list_goods, methods=['GET'])
        app.add_api_route(
            '/catalogue/goods/{candidate_id}', self._get_good, methods=['GET']
        )
        app.add_api_route(
            '/catalogue/goods/{candidate_id}/preview',
            self._get_good_preview,
            methods=['GET'],
        )
        app.add_api_route('/auth/register', self._register, methods=['POST'])
        app.add_api_route('/auth/session', self._sign_in, methods=['POST'])
        app.add_api_route('/auth/session', self._sign_out, methods=['DELETE'])
        app.add_api_route(
            '/auth/me',
            self._me,
            methods=['GET'],
            dependencies=[Depends(self._require_buyer)],
        )
        app.add_api_route(
            '/auth/password',
            self._change_password,
            methods=['POST'],
            dependencies=[Depends(self._require_buyer)],
        )
        app.add_api_route(
            '/account/goods/{candidate_id}/grant',
            self._issue_grant,
            methods=['POST'],
            dependencies=[Depends(self._require_buyer)],
        )
        app.add_api_route(
            '/downloads/{token}',
            self._download,
            methods=['GET'],
            dependencies=[Depends(self._require_buyer)],
        )
        app.add_api_route(
            '/account/entitlements',
            self._list_entitlements,
            methods=['GET'],
            dependencies=[Depends(self._require_buyer)],
        )
        app.add_api_route(
            '/account/orders',
            self._list_orders,
            methods=['GET'],
            dependencies=[Depends(self._require_buyer)],
        )
        app.add_api_route(
            '/account/orders/{order_id}',
            self._get_order,
            methods=['GET'],
            dependencies=[Depends(self._require_buyer)],
        )
        app.add_api_route(
            '/checkout/disclosure', self._checkout_disclosure, methods=['GET']
        )
        app.add_api_route(
            '/checkout/providers', self._checkout_providers, methods=['GET']
        )
        app.add_api_route(
            '/checkout/start',
            self._checkout_start,
            methods=['POST'],
            dependencies=[Depends(self._require_buyer)],
        )
        app.add_api_route('/webhooks/stripe', self._stripe_webhook, methods=['POST'])
        app.add_api_route('/webhooks/bepaid', self._bepaid_webhook, methods=['POST'])
        if self._stub is not None:
            app.add_api_route('/webhooks/stub', self._stub_webhook, methods=['POST'])
        app.add_api_route(
            '/ops/orders/{order_id}/refund', self._operator_refund, methods=['POST']
        )
        return app

    def _cors_origins(self) -> list[str]:
        origins = list(self._origins_from_storefront_domain())
        if self._environment == 'dev':
            origins.extend(self.DEV_STOREFRONT_ORIGINS)
        return origins

    def _origins_from_storefront_domain(self) -> tuple[str, ...]:
        domain = self._storefront_domain
        if domain.startswith('http://') or domain.startswith('https://'):
            return (domain,)
        return (f'https://{domain}', f'http://{domain}')

    async def _health(self) -> dict[str, str]:
        return {'status': 'ok', 'environment': self._environment}

    async def _root(self) -> JSONResponse:
        """Name the service so an operator has a discovery point.

        It carries no good, no count and no URL: the catalogue is a JSON route a
        buyer's storefront reads, and the root must not become a second, ungated
        listing of it.
        """
        return JSONResponse({'service': self.SERVICE_NAME, 'status': 'ok'})

    async def _register(self, body: RegisterBody) -> JSONResponse:
        """Create the account, sign the buyer in and return the profile.

        A refusal is one of ``AccountService``'s codes, mapped by ``_refusal``
        to the fixed body and status. Nothing on the path echoes the password.
        """
        outcome = await self._accounts.register(
            body.email, body.password, body.display_name
        )
        if outcome.reason is not None:
            return self._refusal(outcome.reason)
        response = JSONResponse(
            self._profile_payload(outcome.account), status_code=201
        )
        self._set_session_cookie(response, outcome.token)
        return response

    async def _sign_in(self, body: SignInBody) -> JSONResponse:
        outcome = await self._accounts.sign_in(body.email, body.password)
        if outcome.reason is not None:
            return self._refusal(outcome.reason)
        response = JSONResponse(self._profile_payload(outcome.account))
        self._set_session_cookie(response, outcome.token)
        return response

    async def _sign_out(self, request: Request) -> JSONResponse:
        """Revoke the presented session and clear the cookie.

        Signing out is idempotent: with no session there is nothing to revoke and
        the cookie is still cleared, so a buyer cannot be left holding a stale
        cookie by pressing sign out after their session already expired.
        """
        token = request.cookies.get(self._session_cookie_name)
        if token is not None and token != '':
            await self._accounts.sign_out(token)
        response = JSONResponse({'ok': True})
        self._clear_session_cookie(response)
        return response

    async def _me(self, request: Request) -> JSONResponse:
        account: Account = request.state.buyer
        return JSONResponse(self._profile_payload(account))

    async def _change_password(
        self, request: Request, body: ChangePasswordBody
    ) -> JSONResponse:
        account: Account = request.state.buyer
        token: str = request.state.session_token
        outcome = await self._accounts.change_password(
            account.account_id, token, body.current_password, body.new_password
        )
        if outcome.reason is not None:
            return self._refusal(outcome.reason)
        return JSONResponse(self._profile_payload(outcome.account))

    def _refusal(self, code: str) -> JSONResponse:
        """The fixed refusal body for one account code.

        ``reason`` is the machine contract and ``detail`` the developer sentence;
        a ``password_too_short`` body carries ``minimum_length`` as its own field
        because the number is the API's, not the code's and not the copy's.
        """
        body: dict[str, object] = {
            'detail': self.REFUSAL_DETAILS[code],
            'reason': code,
        }
        if code == AccountService.PASSWORD_TOO_SHORT:
            body['minimum_length'] = self._password_min_length
        return JSONResponse(body, status_code=self.REFUSAL_STATUSES[code])

    @staticmethod
    def _profile_payload(account: Account) -> dict[str, object]:
        """The buyer's own profile, and nothing that authenticates them."""
        return {
            'id': account.account_id,
            'email': account.email,
            'display_name': account.display_name,
        }

    def _set_session_cookie(self, response: Response, token: str) -> None:
        response.set_cookie(
            key=self._session_cookie_name,
            value=token,
            max_age=self._session_lifetime_seconds,
            httponly=True,
            secure=True,
            samesite='lax',
            path='/',
        )

    def _clear_session_cookie(self, response: Response) -> None:
        response.delete_cookie(
            key=self._session_cookie_name,
            path='/',
            secure=True,
            httponly=True,
            samesite='lax',
        )

    async def _list_categories(
        self, locale: Annotated[Locale, Query()] = DEFAULT_LOCALE
    ) -> JSONResponse:
        summaries = await self._catalogue.category_summaries(locale)
        return JSONResponse([self._category_payload(summary) for summary in summaries])

    async def _get_category(
        self,
        slug: str,
        locale: Annotated[Locale, Query()] = DEFAULT_LOCALE,
        limit: Annotated[int, Query(ge=1, le=60)] = 24,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> JSONResponse:
        page = await self._catalogue.category_page(slug, locale, limit, offset)
        if page is None:
            return JSONResponse({'detail': 'category not found'}, status_code=404)
        payload = self._category_payload(page.summary)
        payload['items'] = [self._card_payload(card) for card in page.items]
        payload['total'] = page.total
        return JSONResponse(payload)

    async def _list_goods(
        self,
        locale: Annotated[Locale, Query()] = DEFAULT_LOCALE,
        q: Annotated[str | None, Query()] = None,
        sort: Annotated[CatalogueSort, Query()] = CatalogueSort.NEWEST,
        category: Annotated[str | None, Query()] = None,
        license: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=60)] = 24,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> JSONResponse:
        """The catalogue page a buyer asked for.

        ``sort`` is validated as an enum and ``limit`` and ``offset`` by their
        bounds, so an out-of-contract query is a 422 at the edge rather than a
        silent fallback to a default the buyer did not choose.
        """
        page = await self._catalogue.page(
            locale, sort, q, category, license, limit, offset
        )
        return JSONResponse(
            {
                'items': [self._card_payload(card) for card in page.items],
                'total': page.total,
                'limit': page.limit,
                'offset': page.offset,
            }
        )

    async def _get_good(
        self, candidate_id: str, locale: Annotated[Locale, Query()] = DEFAULT_LOCALE
    ) -> JSONResponse:
        card = await self._catalogue.card(candidate_id, locale)
        if card is None:
            return JSONResponse({'detail': 'good not found'}, status_code=404)
        return JSONResponse(self._card_payload(card))

    async def _get_good_preview(self, candidate_id: str) -> Response:
        """Serve the bytes a product card or page shows for a good.

        A refusal is not handled here. ``GoodPreview.render`` reports one of five
        documented errors (openspec/specs/commerce/storefront; contract.md, GET
        /catalogue/goods/{candidate_id}/preview) and ``PREVIEW_REFUSALS`` maps each
        to the status code that contract fixes, registered as an exception handler
        in ``build``. Writing the mapping as a table rather than as a chain of
        ``except`` clauses means the route has no catch in it at all, and an error
        that reaches the default handler is a programming mistake rather than a
        buyer-visible state.
        """
        image = await self._preview.render(candidate_id)
        return Response(
            content=image.payload,
            media_type=image.media_type,
            headers={
                'ETag': image.etag,
                'Cache-Control': self.PREVIEW_CACHE_CONTROL,
            },
        )

    @staticmethod
    def _refusal_handler(
        status: int, detail: str
    ) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
        """Build the handler for one documented preview refusal.

        The detail is closed over rather than looked up from ``PREVIEW_REFUSALS``
        at request time, so the body a caller sees is fixed when the table is
        read: a refusal this table does not name has no handler and stays a 500,
        which is the honest signal that the contract and the code disagree.
        Every detail is one of ours and names no origin, which is the part of the
        contract that matters most: a preview is the first time origin bytes
        leave this host before payment, and where they came from is not the
        buyer's business.
        """

        async def handler(_request: Request, _error: Exception) -> JSONResponse:
            return JSONResponse({'detail': detail}, status_code=status)

        return handler

    @staticmethod
    def _card_payload(card: CatalogueCard) -> dict[str, object]:
        return {
            'candidate_id': card.candidate_id,
            'title': card.title,
            'original_title': card.original_title,
            'summary': card.summary,
            'creator': card.creator,
            'license_id': card.license_id,
            'obligations': list(card.obligations),
            'category_id': card.category_id,
            'category_slug': card.category_slug,
            'unit_amount': card.unit_amount,
            'currency': card.currency,
            'preview_url': card.preview_url,
            'preview_is_cover': card.preview_is_cover,
            'content_type': card.content_type,
            'size_bytes': card.size_bytes,
            'published_at': ApiApplication._format_instant(card.published_at),
        }

    @staticmethod
    def _category_payload(summary: CategorySummary) -> dict[str, object]:
        return {
            'category_id': summary.category_id,
            'name': summary.name,
            'slug': summary.slug,
            'count': summary.count,
        }

    async def _issue_grant(self, candidate_id: str, request: Request) -> JSONResponse:
        """Issue a short-lived download grant for an entitled buyer.

        The buyer is the session owner: the route carries the session dependency,
        so ``request.state.buyer`` is set before this runs and no request value
        can name an owner.
        """
        buyer_id = self._buyer_id(request)
        rows = await self._entitlements.for_buyer_candidate(buyer_id, candidate_id)
        if not any(row.state is EntitlementState.ACTIVE for row in rows):
            return JSONResponse(
                {'detail': 'no active entitlement for this good'},
                status_code=403,
            )
        token, grant = self._grants.issue(buyer_id, candidate_id, self._clock())
        return JSONResponse(
            {
                'token': token,
                'expires_at': self._format_instant(grant.expires_at),
            }
        )

    async def _download(self, token: str, request: Request) -> Response:
        """Serve bytes for a verified grant.

        The buyer is the session owner, which is also what makes a download work
        as a browser navigation: the cookie is sent on the navigation, and no
        header is needed.
        """
        buyer_id = self._buyer_id(request)
        # GrantRefusedError / DeliveryRefusedError are the documented refusal
        # contracts of the grant and delivery services; mapping them to HTTP is
        # the route's job (task 4.3 R4 / R6).
        try:
            grant = self._grants.verify(token, buyer_id, self._clock())
        except GrantRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        try:
            result = await self._delivery.deliver(buyer_id, grant.candidate_id)
        except DeliveryRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        filename = f'{grant.candidate_id}.bin'
        return Response(
            content=result.payload,
            media_type='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )

    async def _list_entitlements(self, request: Request) -> JSONResponse:
        buyer_id = self._buyer_id(request)
        rows = await self._entitlements.for_buyer(buyer_id)
        return JSONResponse([self._entitlement_payload(row) for row in rows])

    async def _list_orders(self, request: Request) -> JSONResponse:
        buyer_id = self._buyer_id(request)
        orders = await self._orders.orders_for_buyer(buyer_id)
        return JSONResponse([order.model_dump(mode='json') for order in orders])

    async def _get_order(self, order_id: str, request: Request) -> JSONResponse:
        buyer_id = self._buyer_id(request)
        order = await self._orders.by_order_id(order_id)
        if order is None or order.buyer_id != buyer_id:
            return JSONResponse({'detail': 'order not found'}, status_code=404)
        return JSONResponse(order.model_dump(mode='json'))

    async def _checkout_disclosure(self) -> JSONResponse:
        """Public seller disclosure for the checkout gate (no auth).

        Buyers must read the configured identity before pay. Operator keys and
        payment secrets are never part of this payload.
        """
        row = await self._disclosures.current()
        missing = self._disclosure_check.incomplete(row)
        disclosure = row if row is not None else SellerDisclosure()
        return JSONResponse(
            {
                'complete': len(missing) == 0,
                'missing': [item.value for item in missing],
                'disclosure': disclosure.model_dump(mode='json'),
            }
        )

    async def _checkout_providers(self) -> JSONResponse:
        """List payment providers available for this process.

        ``stub`` appears only when the composition root wired
        ``StubPaymentProvider`` (dev). Other environments never expose it.
        """
        providers = list(self.BASE_PROVIDER_IDS)
        if self._stub is not None:
            providers.append(self._stub.provider_id)
        return JSONResponse(providers)

    async def _checkout_start(
        self, request: Request, body: CheckoutStartBody
    ) -> JSONResponse:
        """Start payment for the posted cart lines.

        There is no server-side cart table in this change: the client POSTs the
        lines (task 5.5 R5 / design of Cart as a value object). The owner is the
        session account, and the session dependency refuses before this runs, so
        no payment is attempted without one.
        """
        buyer_id = self._buyer_id(request)
        cart = Cart(
            buyer_id=buyer_id,
            currency=body.currency,
            lines=tuple(
                CartLine(
                    candidate_id=line.candidate_id,
                    unit_amount=line.unit_amount,
                    quantity=line.quantity,
                )
                for line in body.lines
            ),
        )
        # CheckoutRefusedError is the documented refusal contract of
        # CheckoutService.start; PaymentProviderError is the provider start
        # failure. Mapping them to HTTP is the boundary's job (rule 03:
        # interface translation where a traceback is not useful).
        try:
            order, payment = await self._checkout.start(
                cart, body.provider_id, body.return_url, self._clock()
            )
        except CheckoutRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        except PaymentProviderError as error:
            return JSONResponse({'detail': str(error)}, status_code=502)
        return JSONResponse(
            {
                'order_id': order.order_id,
                'redirect_url': payment.redirect_url,
                'provider_reference': payment.provider_reference,
                'state': order.state.value,
            }
        )

    async def _stripe_webhook(self, request: Request) -> JSONResponse:
        payload = await request.body()
        signature = request.headers.get(self.STRIPE_SIGNATURE_HEADER, '')
        # PaymentNotificationError is the documented auth/parse failure of
        # StripeProvider.parse_notification; CheckoutRefusedError is confirm's
        # refusal. Mapping them to HTTP is the boundary's job (rule 03).
        try:
            confirmation = self._stripe.parse_notification(payload, signature)
        except PaymentNotificationError as error:
            return JSONResponse({'detail': str(error)}, status_code=400)
        try:
            await self._checkout.confirm(confirmation, self._clock())
        except CheckoutRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        return JSONResponse({'ok': True})

    async def _bepaid_webhook(self, request: Request) -> JSONResponse:
        payload = await request.body()
        signature = request.headers.get(self.BEPAID_SIGNATURE_HEADER)
        authorization = request.headers.get(self.AUTHORIZATION_HEADER)
        # PaymentNotificationError is the documented auth/parse failure of
        # BePaidProvider.parse_notification; CheckoutRefusedError is confirm's
        # refusal. Mapping them to HTTP is the boundary's job (rule 03).
        try:
            confirmation = self._bepaid.parse_notification(
                payload, signature, authorization
            )
        except PaymentNotificationError as error:
            return JSONResponse({'detail': str(error)}, status_code=400)
        try:
            await self._checkout.confirm(confirmation, self._clock())
        except CheckoutRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        return JSONResponse({'ok': True})

    async def _stub_webhook(self, request: Request) -> JSONResponse:
        if self._stub is None:
            return JSONResponse({'detail': 'stub provider is not enabled'}, status_code=404)
        payload = await request.body()
        signature = request.headers.get(self.STUB_SIGNATURE_HEADER, '')
        # PaymentNotificationError is the documented auth/parse failure of
        # StubPaymentProvider.parse_notification; CheckoutRefusedError is
        # confirm's refusal. Mapping them to HTTP is the boundary's job
        # (rule 03).
        try:
            confirmation = self._stub.parse_notification(payload, signature)
        except PaymentNotificationError as error:
            return JSONResponse({'detail': str(error)}, status_code=400)
        try:
            await self._checkout.confirm(confirmation, self._clock())
        except CheckoutRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        return JSONResponse({'ok': True})

    async def _operator_refund(
        self, order_id: str, request: Request, body: RefundBody
    ) -> JSONResponse:
        if not self._operator_key_matches(request):
            return JSONResponse(
                {'detail': 'missing or invalid X-Operator-Key header'},
                status_code=401,
            )
        # CheckoutRefusedError is the documented refusal contract of
        # CheckoutService.refund; mapping it to HTTP is the boundary's job
        # (rule 03).
        try:
            order = await self._checkout.refund(order_id, body.reason, self._clock())
        except CheckoutRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        return JSONResponse(order.model_dump(mode='json'))

    def _operator_key_matches(self, request: Request) -> bool:
        if self.OPERATOR_HEADER not in request.headers:
            return False
        provided = request.headers[self.OPERATOR_HEADER]
        if provided == '':
            return False
        expected = self._operator_refund_key.get_secret_value()
        return hmac.compare_digest(provided, expected)

    async def _require_buyer(self, request: Request) -> None:
        """Resolve the session cookie to an account, or refuse as unauthenticated.

        Registered as a route dependency on every route that needs an owner, so
        the refusal happens before the handler runs and before any payment is
        attempted. It writes ``buyer`` and ``session_token`` onto the request
        state; ``_buyer_id`` reads the former, and the password change reads the
        latter to revoke the account's other sessions. There is no header and no
        caller-supplied identity anywhere on this path.
        """
        token = request.cookies.get(self._session_cookie_name)
        if token is None or token == '':
            raise UnauthenticatedError()
        account = await self._accounts.authenticate(token)
        if account is None:
            raise UnauthenticatedError()
        request.state.buyer = account
        request.state.session_token = token

    @staticmethod
    def _buyer_id(request: Request) -> str:
        account: Account = request.state.buyer
        return account.account_id

    async def _unauthenticated_handler(
        self, _request: Request, _error: Exception
    ) -> JSONResponse:
        return JSONResponse(
            {'detail': self.UNAUTHENTICATED_DETAIL, 'reason': self.UNAUTHENTICATED},
            status_code=401,
        )

    @staticmethod
    def _entitlement_payload(row: Entitlement) -> dict[str, object]:
        payload: dict[str, object] = {
            'buyer_id': row.buyer_id,
            'candidate_id': row.candidate_id,
            'order_id': row.order_id,
            'granted_at': ApiApplication._format_instant(row.granted_at),
            'state': row.state.value,
        }
        if row.revocation_reason is not None:
            payload['revocation_reason'] = row.revocation_reason
        if row.revoked_at is not None:
            payload['revoked_at'] = ApiApplication._format_instant(row.revoked_at)
        return payload

    @staticmethod
    def _format_instant(instant: datetime) -> str:
        return instant.astimezone(UTC).isoformat().replace('+00:00', 'Z')
