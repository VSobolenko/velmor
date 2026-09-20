"""The Proofbasket storefront: the goods the publication gate approved.

This module renders; it does not decide. It is handed a ``StorefrontCatalog``,
whose only query is over the gate's own ``publishable`` column, so there is no
code path here that could list a good the gate refused. Every value that came
from a third party - a title, a creator, a URL - is escaped on the way into the
markup, because those strings are written by strangers.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal
from html import escape

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, SecretStr

from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.disclosure import SellerDisclosureCheck
from packages.services.src.commerce.errors import (
    CheckoutRefusedError,
    DeliveryRefusedError,
    GrantRefusedError,
)
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.cart import Cart, CartLine
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.category import Category
from packages.services.src.domain.entitlement import Entitlement, EntitlementState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.domain.seller import SellerDisclosure
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.errors import (
    PaymentNotificationError,
    PaymentProviderError,
)
from packages.services.src.payments.stripe_provider import StripeProvider
from packages.services.src.payments.stub_provider import StubPaymentProvider
from packages.services.src.persistence.contract import (
    CandidateRepository,
    CatalogueEntryRepository,
    CategoryRepository,
    EntitlementRepository,
    OrderRepository,
    SellerDisclosureRepository,
    StorefrontCatalog,
)

Good = tuple[Candidate, RightsRecord]
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


class StorefrontPage:
    """The catalogue page: one card per published good."""

    TITLE = 'Proofbasket'
    SUBTITLE = 'Goods that passed the Velmor rights gate.'
    EMPTY = (
        'Nothing has passed the gate yet. Run discovery, then verification, and the '
        'goods that are provably sellable appear here.'
    )
    NOTICE = (
        'Read-only catalogue. Payment and checkout are not implemented: this page '
        'records what may be sold, it does not sell it.'
    )
    UNKNOWN_CREATOR = 'Unknown creator'
    NO_LICENCE = 'no licence'

    STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.55;
  color: #14161a;
  background: #f6f7f9;
}
header {
  padding: 2.5rem 1.5rem 1.75rem;
  background: #14161a;
  color: #ffffff;
}
header h1 { margin: 0 0 .35rem; font-size: 1.9rem; letter-spacing: -.02em; }
header p { margin: 0; color: #b9bfc9; }
.count { margin-top: .85rem !important; color: #ffffff !important; font-weight: 600; }
main {
  display: grid;
  gap: 1.25rem;
  grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
  padding: 2rem 1.5rem 3rem;
  max-width: 74rem;
  margin: 0 auto;
}
.card {
  background: #ffffff;
  border: 1px solid #e2e5ea;
  border-radius: .6rem;
  padding: 1.15rem 1.25rem 1.25rem;
  display: flex;
  flex-direction: column;
}
.card h2 { margin: 0 0 .3rem; font-size: 1.05rem; line-height: 1.35; }
.creator { margin: 0 0 .8rem; color: #626a76; font-size: .9rem; }
.badges { margin: 0 0 .9rem; display: flex; flex-wrap: wrap; gap: .4rem; }
.badge {
  display: inline-block;
  padding: .2rem .55rem;
  border-radius: 999px;
  background: #eef1f5;
  color: #2a3038;
  font-size: .78rem;
  font-weight: 600;
}
.verdict { background: #e3f3e8; color: #1d6b37; }
.obligations { margin-top: auto; }
.obligations h3 {
  margin: 0 0 .35rem;
  font-size: .74rem;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: #767d89;
}
.obligations ul { margin: 0; padding-left: 1.1rem; font-size: .87rem; }
.obligations p { margin: 0; font-size: .87rem; color: #626a76; }
.links { margin: 1rem 0 0; font-size: .87rem; }
.links a { color: #1a5fb4; }
.empty {
  grid-column: 1 / -1;
  background: #ffffff;
  border: 1px dashed #c8cdd5;
  border-radius: .6rem;
  padding: 2rem 1.5rem;
  color: #626a76;
}
footer {
  padding: 1.25rem 1.5rem 2.5rem;
  color: #767d89;
  font-size: .84rem;
  text-align: center;
}
"""

    def render(self, goods: tuple[Good, ...], total: int) -> str:
        if goods:
            body = '\n'.join(self._card(candidate, record) for candidate, record in goods)
        else:
            body = f'<p class="empty">{escape(self.EMPTY)}</p>'
        return self._document(body, shown=len(goods), total=total)

    def _document(self, body: str, shown: int, total: int) -> str:
        return (
            '<!DOCTYPE html>'
            '<html lang="en">'
            '<head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(self.TITLE)}</title>'
            f'<style>{self.STYLE}</style>'
            '</head>'
            '<body>'
            '<header>'
            f'<h1>{escape(self.TITLE)}</h1>'
            f'<p>{escape(self.SUBTITLE)}</p>'
            f'<p class="count">{self._count(shown, total)}</p>'
            '</header>'
            f'<main>{body}</main>'
            f'<footer>{escape(self.NOTICE)}</footer>'
            '</body>'
            '</html>'
        )

    def _count(self, shown: int, total: int) -> str:
        if shown == total:
            return escape(f'{total} approved for sale')
        return escape(f'{total} approved for sale, showing the {shown} most recent')

    def _card(self, candidate: Candidate, record: RightsRecord) -> str:
        return (
            '<article class="card">'
            f'<h2>{escape(candidate.title)}</h2>'
            f'<p class="creator">{self._creator(candidate)}</p>'
            f'<p class="badges">{self._badges(record)}</p>'
            f'{self._obligations(record)}'
            f'<p class="links">{self._links(candidate)}</p>'
            '</article>'
        )

    def _creator(self, candidate: Candidate) -> str:
        if candidate.creator is None:
            return escape(self.UNKNOWN_CREATOR)
        return escape(candidate.creator)

    def _badges(self, record: RightsRecord) -> str:
        licence = record.license_id or self.NO_LICENCE
        return (
            f'<span class="badge">{escape(licence)}</span>'
            f'<span class="badge verdict">{escape(record.verdict.value)}</span>'
        )

    def _obligations(self, record: RightsRecord) -> str:
        if record.obligations:
            items = ''.join(f'<li>{escape(item)}</li>' for item in record.obligations)
            content = f'<ul>{items}</ul>'
        else:
            content = '<p>None</p>'
        return f'<div class="obligations"><h3>Obligations</h3>{content}</div>'

    def _links(self, candidate: Candidate) -> str:
        source = f'<a href="{escape(candidate.landing_url, quote=True)}">Source page</a>'
        if candidate.download_url is None:
            return source
        download = (
            f'<a href="{escape(candidate.download_url, quote=True)}">Download</a>'
        )
        return f'{source} &middot; {download}'


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


class ApiApplication:
    """The HTTP surface of the platform.

    Routes are registered as bound methods rather than decorated module-level
    functions, so the handlers can read the injected catalogue without a global.
    """

    CATALOGUE_LIMIT = 100
    BROWSE_LIMIT = 200
    BUYER_HEADER = 'x-buyer-id'
    OPERATOR_HEADER = 'x-operator-key'
    STRIPE_SIGNATURE_HEADER = 'stripe-signature'
    BEPAID_SIGNATURE_HEADER = 'content-signature'
    STUB_SIGNATURE_HEADER = 'x-stub-signature'
    AUTHORIZATION_HEADER = 'authorization'
    CORS_ALLOW_METHODS = ('GET', 'POST', 'OPTIONS')
    CORS_ALLOW_HEADERS = (
        'X-Buyer-Id',
        'Content-Type',
        'Authorization',
        'X-Stub-Signature',
    )
    DEV_STOREFRONT_ORIGINS = (
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    )
    BASE_PROVIDER_IDS = ('stripe', 'bepaid')

    def __init__(
        self,
        environment: str,
        catalog: StorefrontCatalog,
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
        entries: CatalogueEntryRepository,
        categories: CategoryRepository,
        candidates: CandidateRepository,
        catalogue_unit_amount: Decimal,
        catalogue_currency: str,
        storefront_domain: str,
        stub: StubPaymentProvider | None = None,
        lifespan: Lifespan | None = None,
    ) -> None:
        self._environment = environment
        self._catalog = catalog
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
        self._entries = entries
        self._categories = categories
        self._candidates = candidates
        self._catalogue_unit_amount = catalogue_unit_amount
        self._catalogue_currency = catalogue_currency
        self._storefront_domain = storefront_domain
        self._lifespan = lifespan
        self._page = StorefrontPage()

    def build(self) -> FastAPI:
        app = FastAPI(
            title=StorefrontPage.TITLE,
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
        app.add_api_route(
            '/', self._storefront, methods=['GET'], response_class=HTMLResponse
        )
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
            '/account/goods/{candidate_id}/grant',
            self._issue_grant,
            methods=['POST'],
        )
        app.add_api_route('/downloads/{token}', self._download, methods=['GET'])
        app.add_api_route(
            '/account/entitlements', self._list_entitlements, methods=['GET']
        )
        app.add_api_route('/account/orders', self._list_orders, methods=['GET'])
        app.add_api_route(
            '/account/orders/{order_id}', self._get_order, methods=['GET']
        )
        app.add_api_route(
            '/checkout/disclosure', self._checkout_disclosure, methods=['GET']
        )
        app.add_api_route(
            '/checkout/providers', self._checkout_providers, methods=['GET']
        )
        app.add_api_route('/checkout/start', self._checkout_start, methods=['POST'])
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

    async def _storefront(self) -> HTMLResponse:
        goods = await self._catalog.published(self.CATALOGUE_LIMIT)
        total = await self._catalog.published_count()
        return HTMLResponse(self._page.render(goods, total))

    async def _list_categories(self) -> JSONResponse:
        categories = await self._categories.all()
        return JSONResponse(
            [self._category_summary(category) for category in categories]
        )

    async def _get_category(self, slug: str) -> JSONResponse:
        category = await self._categories.by_slug(slug)
        if category is None:
            return JSONResponse({'detail': 'category not found'}, status_code=404)
        entries = await self._entries.by_category(category.category_id)
        goods = [
            await self._product_dto(entry)
            for entry in entries
            if self._is_saleable(entry)
        ]
        return JSONResponse(
            {
                **self._category_summary(category),
                'goods': goods,
            }
        )

    async def _list_goods(self) -> JSONResponse:
        entries = await self._entries.entries(self.BROWSE_LIMIT)
        goods = [
            await self._product_dto(entry)
            for entry in entries
            if self._is_saleable(entry)
        ]
        return JSONResponse(goods)

    async def _get_good(self, candidate_id: str) -> JSONResponse:
        entry = await self._entries.by_candidate(candidate_id)
        if entry is None or not self._is_saleable(entry):
            return JSONResponse({'detail': 'good not found'}, status_code=404)
        return JSONResponse(await self._product_dto(entry))

    @staticmethod
    def _is_saleable(entry: CatalogueEntry) -> bool:
        return (
            entry.state is CatalogueEntryState.PUBLISHED
            and entry.listing is StorefrontListing.PAID_OK
        )

    @staticmethod
    def _category_summary(category: Category) -> dict[str, str]:
        return {
            'category_id': category.category_id,
            'name': category.name,
            'slug': category.slug,
        }

    async def _product_dto(self, entry: CatalogueEntry) -> dict[str, object]:
        candidate = await self._candidates.by_candidate_id(entry.candidate_id)
        if candidate is None:
            raise RuntimeError(
                f'catalogue entry {entry.candidate_id} has no candidate row'
            )
        category_slug: str | None = None
        if entry.category_id is not None:
            category = await self._categories.by_id(entry.category_id)
            if category is not None:
                category_slug = category.slug
        return {
            'candidate_id': entry.candidate_id,
            'title': candidate.title,
            'creator': candidate.creator,
            'license_id': entry.license_id,
            'obligations': list(entry.obligations),
            'category_id': entry.category_id,
            'category_slug': category_slug,
            'unit_amount': format(self._catalogue_unit_amount, 'f'),
            'currency': self._catalogue_currency,
        }

    async def _issue_grant(self, candidate_id: str, request: Request) -> JSONResponse:
        """Issue a short-lived download grant for an entitled buyer.

        Buyer identity is taken from the temporary ``X-Buyer-Id`` header.
        Saleor/customer session auth is deferred to storefront work (group 6);
        this route keeps the stand-in rather than inventing a session store.
        """
        buyer_id = self._require_buyer_id(request)
        if buyer_id is None:
            return JSONResponse(
                {'detail': 'missing or empty X-Buyer-Id header'},
                status_code=401,
            )
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

        Buyer identity is taken from the temporary ``X-Buyer-Id`` header.
        Saleor/customer session auth is deferred to storefront work (group 6).
        """
        buyer_id = self._require_buyer_id(request)
        if buyer_id is None:
            return JSONResponse(
                {'detail': 'missing or empty X-Buyer-Id header'},
                status_code=401,
            )
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
        buyer_id = self._require_buyer_id(request)
        if buyer_id is None:
            return JSONResponse(
                {'detail': 'missing or empty X-Buyer-Id header'},
                status_code=401,
            )
        rows = await self._entitlements.for_buyer(buyer_id)
        return JSONResponse([self._entitlement_payload(row) for row in rows])

    async def _list_orders(self, request: Request) -> JSONResponse:
        buyer_id = self._require_buyer_id(request)
        if buyer_id is None:
            return JSONResponse(
                {'detail': 'missing or empty X-Buyer-Id header'},
                status_code=401,
            )
        orders = await self._orders.orders_for_buyer(buyer_id)
        return JSONResponse([order.model_dump(mode='json') for order in orders])

    async def _get_order(self, order_id: str, request: Request) -> JSONResponse:
        buyer_id = self._require_buyer_id(request)
        if buyer_id is None:
            return JSONResponse(
                {'detail': 'missing or empty X-Buyer-Id header'},
                status_code=401,
            )
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
        lines (task 5.5 R5 / design of Cart as a value object).
        """
        buyer_id = self._require_buyer_id(request)
        if buyer_id is None:
            return JSONResponse(
                {'detail': 'missing or empty X-Buyer-Id header'},
                status_code=401,
            )
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

    def _require_buyer_id(self, request: Request) -> str | None:
        if self.BUYER_HEADER not in request.headers:
            return None
        buyer_id = request.headers[self.BUYER_HEADER]
        if buyer_id == '':
            return None
        return buyer_id

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
