from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from packages.api.src.app import ApiApplication
from packages.api.tests.unit.storefront_services import (
    TEST_PASSWORD_MIN_LENGTH,
    TEST_SESSION_COOKIE_NAME,
    TEST_SESSION_LIFETIME_SECONDS,
    build_accounts,
    build_catalogue,
    build_preview,
)
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.stripe_provider import StripeProvider
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.unit.payments.test_bepaid_provider import (
    PUBLIC_KEY_PEM as BEPAID_PUBLIC_KEY_PEM,
)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
OPERATOR_KEY = SecretStr('api-unit-operator-refund-key')
GRANT_SECRET = SecretStr('api-unit-delivery-grant-secret')
UNIT_AMOUNT = Decimal('9.99')
CURRENCY = 'USD'
STOREFRONT_DOMAIN = 'shop.example'
DEV_ORIGIN = 'http://localhost:3000'
DISALLOWED_ORIGIN = 'https://evil.example'


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant


def build_client(*, environment: str, storefront_domain: str, tmp_path: Path) -> TestClient:
    store = InMemoryStore()
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=b''))
    )
    stripe = StripeProvider(
        secret_key=SecretStr('sk_test_cors'),
        webhook_secret=SecretStr('whsec_cors'),
        http=http,
    )
    bepaid = BePaidProvider(
        shop_id='cors-shop',
        secret_key=SecretStr('bepaid_cors'),
        public_key_pem=BEPAID_PUBLIC_KEY_PEM,
        http=http,
        notification_url='https://shop.example/webhooks/bepaid',
    )
    checkout = CheckoutService(
        entries=store,
        disclosures=store,
        orders=store,
        entitlements=store,
        providers={'stripe': stripe, 'bepaid': bepaid},
    )
    grants = DeliveryGrantService(secret=GRANT_SECRET, lifetime_seconds=900)
    cache = AssetCache(root=tmp_path, max_bytes=1024)
    delivery = DeliveryService(
        entitlements=store,
        entries=store,
        cache=cache,
        http=http,
    )
    return TestClient(
        ApiApplication(
            environment,
            grants=grants,
            delivery=delivery,
            entitlements=store,
            clock=FixedClock(NOW),
            checkout=checkout,
            disclosures=store,
            stripe=stripe,
            bepaid=bepaid,
            orders=store,
            operator_refund_key=OPERATOR_KEY,
            catalogue=build_catalogue(store, UNIT_AMOUNT, CURRENCY),
            preview=build_preview(store, cache, http),
            storefront_domain=storefront_domain,
            accounts=build_accounts(store, FixedClock(NOW)),
            session_cookie_name=TEST_SESSION_COOKIE_NAME,
            session_lifetime_seconds=TEST_SESSION_LIFETIME_SECONDS,
            password_min_length=TEST_PASSWORD_MIN_LENGTH,
        ).build()
    )


class TestCorsPreflight:
    def test_dev_allows_localhost_storefront_origin(self, tmp_path: Path) -> None:
        client = build_client(
            environment='dev',
            storefront_domain=STOREFRONT_DOMAIN,
            tmp_path=tmp_path,
        )

        response = client.options(
            '/account/entitlements',
            headers={
                'Origin': DEV_ORIGIN,
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'content-type',
            },
        )

        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == DEV_ORIGIN
        allow_headers = response.headers['access-control-allow-headers'].lower()
        assert 'content-type' in allow_headers

    def test_disallowed_origin_is_not_reflected(self, tmp_path: Path) -> None:
        client = build_client(
            environment='dev',
            storefront_domain=STOREFRONT_DOMAIN,
            tmp_path=tmp_path,
        )

        response = client.options(
            '/account/entitlements',
            headers={
                'Origin': DISALLOWED_ORIGIN,
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'content-type',
            },
        )

        allow_origin = response.headers.get('access-control-allow-origin')
        assert allow_origin is None or allow_origin == ''
        assert allow_origin != '*'

    def test_bare_storefront_domain_allows_https_origin(self, tmp_path: Path) -> None:
        client = build_client(
            environment='test',
            storefront_domain=STOREFRONT_DOMAIN,
            tmp_path=tmp_path,
        )
        origin = f'https://{STOREFRONT_DOMAIN}'

        response = client.options(
            '/account/goods/openverse:1/grant',
            headers={
                'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
            },
        )

        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == origin
