from __future__ import annotations

import hashlib
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient
from pydantic import SecretStr

from packages.api.src.app import ApiApplication
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.disclosure import SellerDisclosureCheck
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.entitlement import EntitlementState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.order import OrderState
from packages.services.src.domain.seller import SellerDisclosure, SellerDisclosureItem
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.stripe_provider import StripeProvider
from packages.services.src.payments.stub_provider import StubPaymentProvider
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate, build_record
from packages.services.tests.unit.payments.test_stripe_provider import (
    completed_event_payload,
)
from packages.services.tests.unit.payments.test_stripe_provider import (
    sign_payload as stripe_sign_payload,
)
from packages.services.tests.unit.payments.test_stub_provider import (
    sign_payload as stub_sign_payload,
)
from packages.services.tests.unit.payments.test_stub_provider import (
    success_payload as stub_success_payload,
)

ORIGIN_URL = 'https://secret-origin.example/never-leak/asset.bin'
BUYER_ID = 'buyer-1'
OTHER_BUYER = 'buyer-2'
CANDIDATE_ID = 'openverse:1'
DIGEST = hashlib.sha256(b'commerce-api-bytes').hexdigest()
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
EARLIER = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)
GRANT_SECRET = SecretStr('api-commerce-grant-secret')
OPERATOR_KEY = SecretStr('operator-refund-key-unit-test')
STRIPE_SECRET = SecretStr('sk_test_commerce_api_not_real')
STRIPE_WEBHOOK = SecretStr('whsec_commerce_api_webhook_secret')
STUB_WEBHOOK = SecretStr('stub_commerce_api_webhook_secret')
BEPAID_SHOP = 'bepaid-shop-commerce'
BEPAID_SECRET = SecretStr('bepaid_secret_commerce_api')
BEPAID_NOTIFICATION = 'https://shop.example/webhooks/bepaid'
SESSION_URL = 'https://checkout.stripe.com/c/pay/cs_test_commerce'
SESSION_ID = 'cs_test_commerce_session'
RETURN_URL = 'https://shop.example/return'
UNIT_AMOUNT = Decimal('10.50')
CURRENCY = 'USD'
BUYER_HEADER = 'X-Buyer-Id'
OPERATOR_HEADER = 'X-Operator-Key'


def _rsa_keypair() -> tuple[str, rsa.RSAPrivateKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode('utf-8')
    )
    return public_pem, private_key


BEPAID_PUBLIC_PEM, BEPAID_PRIVATE = _rsa_keypair()


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant


class _StaticCatalog:
    def __init__(self, goods: tuple = ()) -> None:
        self._goods = goods

    async def published(self, limit: int) -> tuple:
        return self._goods[:limit]

    async def published_count(self) -> int:
        return len(self._goods)


def build_disclosure() -> SellerDisclosure:
    return SellerDisclosure(
        legal_name='Velmor LLC',
        registration_number='100200300',
        registration_date=date(2026, 1, 15),
        registration_authority='Minsk City Executive Committee',
        shop_register_number='SHOP-1',
        postal_address='Minsk, Belarus',
        working_hours='Mon-Fri 09:00-18:00',
        contact_details='support@velmor.example',
        payment_rules='Payment by card at checkout',
        return_rules='Digital goods are not returnable after download',
        payment_system_marks=('visa', 'mastercard'),
    )


def build_entry(
    *,
    listing: StorefrontListing = StorefrontListing.PAID_OK,
    state: CatalogueEntryState = CatalogueEntryState.PUBLISHED,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=CANDIDATE_ID,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=('Credit the creator',),
        listing=listing,
        state=state,
        withdrawal_reason='withdrawn for test' if state is CatalogueEntryState.WITHDRAWN else None,
        published_at=EARLIER,
        content_digest=DIGEST,
        origin_url=ORIGIN_URL,
    )


def bepaid_sign(payload: bytes) -> str:
    import base64

    signature = BEPAID_PRIVATE.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode('ascii')


def bepaid_success_payload(*, order_id: str, amount: int = 1050) -> bytes:
    import json

    body = {
        'transaction': {
            'uid': 'bepaid-uid-commerce',
            'status': 'successful',
            'amount': amount,
            'currency': 'USD',
            'tracking_id': order_id,
            'type': 'payment',
        }
    }
    return json.dumps(body, separators=(',', ':')).encode('utf-8')


class CommerceHarness:
    def __init__(self, tmp_path: Path, *, enable_stub: bool = False) -> None:
        self.store = InMemoryStore()
        self.clock = FixedClock(NOW)
        self.stripe_calls: list[httpx.Request] = []

        def stripe_handler(request: httpx.Request) -> httpx.Response:
            self.stripe_calls.append(request)
            return httpx.Response(
                200,
                json={'id': SESSION_ID, 'url': SESSION_URL, 'object': 'checkout.session'},
            )

        self.http = httpx.AsyncClient(transport=httpx.MockTransport(stripe_handler))
        self.stripe = StripeProvider(
            secret_key=STRIPE_SECRET,
            webhook_secret=STRIPE_WEBHOOK,
            http=self.http,
        )
        self.bepaid = BePaidProvider(
            shop_id=BEPAID_SHOP,
            secret_key=BEPAID_SECRET,
            public_key_pem=BEPAID_PUBLIC_PEM,
            http=self.http,
            notification_url=BEPAID_NOTIFICATION,
        )
        providers: dict[str, object] = {'stripe': self.stripe, 'bepaid': self.bepaid}
        self.stub: StubPaymentProvider | None = None
        if enable_stub:
            self.stub = StubPaymentProvider(webhook_secret=STUB_WEBHOOK)
            providers['stub'] = self.stub
        self.checkout = CheckoutService(
            entries=self.store,
            disclosures=self.store,
            orders=self.store,
            entitlements=self.store,
            providers=providers,
        )
        grants = DeliveryGrantService(secret=GRANT_SECRET, lifetime_seconds=900)
        cache = AssetCache(root=tmp_path, max_bytes=1024)
        delivery = DeliveryService(
            entitlements=self.store,
            entries=self.store,
            cache=cache,
            http=self.http,
        )
        catalog = _StaticCatalog(((build_candidate(candidate_id=CANDIDATE_ID), build_record()),))
        self.client = TestClient(
            ApiApplication(
                'test',
                catalog,
                grants=grants,
                delivery=delivery,
                entitlements=self.store,
                clock=self.clock,
                checkout=self.checkout,
                disclosures=self.store,
                stripe=self.stripe,
                bepaid=self.bepaid,
                orders=self.store,
                operator_refund_key=OPERATOR_KEY,
                entries=self.store,
                categories=self.store,
                candidates=self.store,
                catalogue_unit_amount=UNIT_AMOUNT,
                catalogue_currency=CURRENCY,
                storefront_domain='shop.example',
                stub=self.stub,
            ).build()
        )

    def start_body(
        self,
        *,
        provider_id: str = 'stripe',
        currency: str = CURRENCY,
        unit_amount: str = '10.50',
    ) -> dict:
        return {
            'provider_id': provider_id,
            'return_url': RETURN_URL,
            'currency': currency,
            'lines': [
                {
                    'candidate_id': CANDIDATE_ID,
                    'unit_amount': unit_amount,
                    'quantity': 1,
                }
            ],
        }


class TestCheckoutDisclosure:
    async def test_absent_disclosure_names_every_item(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)

        response = harness.client.get('/checkout/disclosure')

        assert response.status_code == 200
        body = response.json()
        assert body['complete'] is False
        assert body['missing'] == [
            item.value for item in SellerDisclosureCheck.REQUIRED_ITEMS
        ]
        assert body['disclosure'] == {
            'legal_name': None,
            'registration_number': None,
            'registration_date': None,
            'registration_authority': None,
            'shop_register_number': None,
            'postal_address': None,
            'working_hours': None,
            'contact_details': None,
            'payment_rules': None,
            'return_rules': None,
            'payment_system_marks': [],
        }
        assert 'operator' not in response.text.lower()
        assert 'secret' not in response.text.lower()
        assert 'sk_test' not in response.text
        assert 'bepaid_secret' not in response.text

    async def test_incomplete_disclosure_names_missing_items(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        incomplete = build_disclosure().model_copy(
            update={'legal_name': None, 'payment_rules': None}
        )
        await harness.store.save_disclosure(incomplete)

        response = harness.client.get('/checkout/disclosure')

        assert response.status_code == 200
        body = response.json()
        assert body['complete'] is False
        assert body['missing'] == [
            SellerDisclosureItem.LEGAL_NAME.value,
            SellerDisclosureItem.PAYMENT_RULES.value,
        ]
        assert body['disclosure']['registration_number'] == '100200300'
        assert body['disclosure']['legal_name'] is None

    async def test_complete_disclosure_is_readable(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())

        response = harness.client.get('/checkout/disclosure')

        assert response.status_code == 200
        body = response.json()
        assert body['complete'] is True
        assert body['missing'] == []
        assert body['disclosure']['legal_name'] == 'Velmor LLC'
        assert body['disclosure']['registration_date'] == '2026-01-15'
        assert body['disclosure']['payment_system_marks'] == ['visa', 'mastercard']
        assert 'operator' not in response.text.lower()
        assert 'sk_test' not in response.text
        assert OPERATOR_KEY.get_secret_value() not in response.text


class TestCheckoutStart:
    async def test_checkout_start_happy_returns_redirect(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry())

        response = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(),
        )

        assert response.status_code == 200
        body = response.json()
        assert body['redirect_url'] == SESSION_URL
        assert body['provider_reference'] == SESSION_ID
        assert body['state'] == OrderState.PENDING.value
        assert body['order_id']
        assert len(harness.stripe_calls) == 1

    async def test_checkout_start_incomplete_disclosure_is_403(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_entry(build_entry())

        response = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(),
        )

        assert response.status_code == 403
        assert 'detail' in response.json()
        assert harness.stripe_calls == []

    async def test_checkout_start_free_only_or_withdrawn_is_403(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry(listing=StorefrontListing.FREE_ONLY))

        free_response = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(),
        )
        assert free_response.status_code == 403
        assert harness.stripe_calls == []

        await harness.store.save_entry(
            build_entry(state=CatalogueEntryState.WITHDRAWN)
        )
        withdrawn_response = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(),
        )
        assert withdrawn_response.status_code == 403
        assert harness.stripe_calls == []


class TestStripeWebhook:
    async def test_valid_signature_marks_paid_and_is_idempotent(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry())
        start = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(),
        )
        order_id = start.json()['order_id']
        payload = completed_event_payload(
            amount_total=1050,
            currency='usd',
            order_id=order_id,
            session_id=SESSION_ID,
        )
        signature = stripe_sign_payload(
            payload, STRIPE_WEBHOOK.get_secret_value(), timestamp=int(time.time())
        )

        first = harness.client.post(
            '/webhooks/stripe',
            content=payload,
            headers={'Stripe-Signature': signature, 'Content-Type': 'application/json'},
        )
        second = harness.client.post(
            '/webhooks/stripe',
            content=payload,
            headers={'Stripe-Signature': signature, 'Content-Type': 'application/json'},
        )

        assert first.status_code == 200
        assert first.json() == {'ok': True}
        assert second.status_code == 200
        order = await harness.store.by_order_id(order_id)
        assert order is not None
        assert order.state is OrderState.PAID
        entitlements = await harness.store.for_buyer(BUYER_ID)
        assert len(entitlements) == 1
        assert entitlements[0].state is EntitlementState.ACTIVE

    async def test_bad_signature_is_400_and_order_unchanged(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry())
        start = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(),
        )
        order_id = start.json()['order_id']
        payload = completed_event_payload(
            amount_total=1050,
            currency='usd',
            order_id=order_id,
            session_id=SESSION_ID,
        )

        response = harness.client.post(
            '/webhooks/stripe',
            content=payload,
            headers={
                'Stripe-Signature': 't=1,v1=deadbeef',
                'Content-Type': 'application/json',
            },
        )

        assert response.status_code == 400
        order = await harness.store.by_order_id(order_id)
        assert order is not None
        assert order.state is OrderState.PENDING
        assert await harness.store.for_buyer(BUYER_ID) == ()


class TestBePaidWebhook:
    async def test_valid_rsa_marks_paid(self, tmp_path: Path) -> None:
        from packages.services.src.domain.order import Order, OrderLine

        harness = CommerceHarness(tmp_path)
        order_id = 'bepaid-order-1'
        await harness.store.save_order(
            Order(
                order_id=order_id,
                buyer_id=BUYER_ID,
                state=OrderState.PENDING,
                currency='USD',
                lines=(
                    OrderLine(
                        candidate_id=CANDIDATE_ID,
                        unit_amount=UNIT_AMOUNT,
                        quantity=1,
                    ),
                ),
                total=UNIT_AMOUNT,
                provider_id='bepaid',
                provider_reference='bepaid-uid-commerce',
                created_at=NOW,
                paid_at=None,
            )
        )
        payload = bepaid_success_payload(order_id=order_id)
        signature = bepaid_sign(payload)

        response = harness.client.post(
            '/webhooks/bepaid',
            content=payload,
            headers={
                'Content-Signature': signature,
                'Content-Type': 'application/json',
            },
        )

        assert response.status_code == 200
        assert response.json() == {'ok': True}
        order = await harness.store.by_order_id(order_id)
        assert order is not None
        assert order.state is OrderState.PAID


class TestStubWebhookAndProviders:
    async def test_providers_omit_stub_when_not_wired(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)

        response = harness.client.get('/checkout/providers')

        assert response.status_code == 200
        assert response.json() == ['stripe', 'bepaid']

    async def test_providers_include_stub_when_wired(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path, enable_stub=True)

        response = harness.client.get('/checkout/providers')

        assert response.status_code == 200
        assert response.json() == ['stripe', 'bepaid', 'stub']

    async def test_valid_stub_signature_marks_paid(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path, enable_stub=True)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry())
        start = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(provider_id='stub'),
        )
        assert start.status_code == 200
        body = start.json()
        order_id = body['order_id']
        assert body['state'] == OrderState.PENDING.value
        assert body['provider_reference'] == f'stub-{order_id}'
        assert f'order_id={order_id}' in body['redirect_url']
        payload = stub_success_payload(
            order_id=order_id,
            amount='10.50',
            currency='USD',
            provider_reference=body['provider_reference'],
        )
        signature = stub_sign_payload(payload, STUB_WEBHOOK.get_secret_value())

        response = harness.client.post(
            '/webhooks/stub',
            content=payload,
            headers={
                'X-Stub-Signature': signature,
                'Content-Type': 'application/json',
            },
        )

        assert response.status_code == 200
        assert response.json() == {'ok': True}
        order = await harness.store.by_order_id(order_id)
        assert order is not None
        assert order.state is OrderState.PAID

    async def test_bad_stub_signature_is_400(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path, enable_stub=True)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry())
        start = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(provider_id='stub'),
        )
        order_id = start.json()['order_id']
        payload = stub_success_payload(
            order_id=order_id,
            amount='10.50',
            currency='USD',
        )

        response = harness.client.post(
            '/webhooks/stub',
            content=payload,
            headers={
                'X-Stub-Signature': 'deadbeef',
                'Content-Type': 'application/json',
            },
        )

        assert response.status_code == 400
        order = await harness.store.by_order_id(order_id)
        assert order is not None
        assert order.state is OrderState.PENDING

    async def test_stub_route_absent_when_not_wired(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        payload = stub_success_payload()

        response = harness.client.post(
            '/webhooks/stub',
            content=payload,
            headers={
                'X-Stub-Signature': stub_sign_payload(
                    payload, STUB_WEBHOOK.get_secret_value()
                ),
                'Content-Type': 'application/json',
            },
        )

        assert response.status_code == 404


class TestAccountRoutes:
    async def test_entitlements_and_orders_are_buyer_scoped(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry())
        start = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(),
        )
        order_id = start.json()['order_id']
        payload = completed_event_payload(
            amount_total=1050,
            currency='usd',
            order_id=order_id,
            session_id=SESSION_ID,
        )
        signature = stripe_sign_payload(
            payload, STRIPE_WEBHOOK.get_secret_value(), timestamp=int(time.time())
        )
        harness.client.post(
            '/webhooks/stripe',
            content=payload,
            headers={'Stripe-Signature': signature, 'Content-Type': 'application/json'},
        )

        mine = harness.client.get(
            '/account/entitlements', headers={BUYER_HEADER: BUYER_ID}
        )
        other = harness.client.get(
            '/account/entitlements', headers={BUYER_HEADER: OTHER_BUYER}
        )
        assert mine.status_code == 200
        assert len(mine.json()) == 1
        assert mine.json()[0]['state'] == EntitlementState.ACTIVE.value
        assert other.status_code == 200
        assert other.json() == []

        orders = harness.client.get(
            '/account/orders', headers={BUYER_HEADER: BUYER_ID}
        )
        assert orders.status_code == 200
        assert len(orders.json()) == 1
        assert orders.json()[0]['order_id'] == order_id

        one = harness.client.get(
            f'/account/orders/{order_id}', headers={BUYER_HEADER: BUYER_ID}
        )
        assert one.status_code == 200
        assert one.json()['order_id'] == order_id

        foreign = harness.client.get(
            f'/account/orders/{order_id}', headers={BUYER_HEADER: OTHER_BUYER}
        )
        assert foreign.status_code == 404


class TestOperatorRefund:
    async def test_correct_key_refunds_wrong_key_is_401(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry())
        start = harness.client.post(
            '/checkout/start',
            headers={BUYER_HEADER: BUYER_ID},
            json=harness.start_body(),
        )
        order_id = start.json()['order_id']
        payload = completed_event_payload(
            amount_total=1050,
            currency='usd',
            order_id=order_id,
            session_id=SESSION_ID,
        )
        signature = stripe_sign_payload(
            payload, STRIPE_WEBHOOK.get_secret_value(), timestamp=int(time.time())
        )
        harness.client.post(
            '/webhooks/stripe',
            content=payload,
            headers={'Stripe-Signature': signature, 'Content-Type': 'application/json'},
        )

        wrong = harness.client.post(
            f'/ops/orders/{order_id}/refund',
            headers={OPERATOR_HEADER: 'wrong-key'},
            json={'reason': 'chargeback'},
        )
        assert wrong.status_code == 401

        missing = harness.client.post(
            f'/ops/orders/{order_id}/refund',
            json={'reason': 'chargeback'},
        )
        assert missing.status_code == 401

        ok = harness.client.post(
            f'/ops/orders/{order_id}/refund',
            headers={OPERATOR_HEADER: OPERATOR_KEY.get_secret_value()},
            json={'reason': 'chargeback'},
        )
        assert ok.status_code == 200
        assert ok.json()['state'] == OrderState.REFUNDED.value
        entitlements = await harness.store.for_buyer(BUYER_ID)
        assert entitlements[0].state is EntitlementState.REVOKED

        grant = harness.client.post(
            f'/account/goods/{CANDIDATE_ID}/grant',
            headers={BUYER_HEADER: BUYER_ID},
        )
        assert grant.status_code == 403
