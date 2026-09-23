from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from packages.api.src.app import ApiApplication
from packages.api.tests.unit.storefront_services import build_catalogue, build_preview
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.entitlement import Entitlement, EntitlementState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.stripe_provider import StripeProvider
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.unit.payments.test_bepaid_provider import (
    PUBLIC_KEY_PEM as BEPAID_PUBLIC_KEY_PEM,
)

ORIGIN_URL = 'https://secret-origin.example/never-leak/asset.bin'
BUYER_ID = 'buyer-1'
OTHER_BUYER = 'buyer-2'
CANDIDATE_ID = 'openverse:1'
PAYLOAD = b'entitled-download-bytes'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
EARLIER = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)
SECRET = SecretStr('api-unit-delivery-grant-secret')
LIFETIME = 900
BUYER_HEADER = 'X-Buyer-Id'
OPERATOR_KEY = SecretStr('api-unit-operator-refund-key')
BEPAID_NOTIFICATION = 'https://shop.example/webhooks/bepaid'
CATALOGUE_UNIT_AMOUNT = Decimal('9.99')
CATALOGUE_CURRENCY = 'USD'


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant


def build_entry(*, origin_url: str = ORIGIN_URL) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=CANDIDATE_ID,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=('Credit the creator',),
        listing=StorefrontListing.PAID_OK,
        state=CatalogueEntryState.PUBLISHED,
        withdrawal_reason=None,
        published_at=EARLIER,
        content_digest=DIGEST,
        origin_url=origin_url,
    )


def build_entitlement(
    *,
    buyer_id: str = BUYER_ID,
    state: EntitlementState = EntitlementState.ACTIVE,
    order_id: str = 'order-1',
    revoked_at: datetime | None = None,
    revocation_reason: str | None = None,
) -> Entitlement:
    return Entitlement(
        buyer_id=buyer_id,
        candidate_id=CANDIDATE_ID,
        order_id=order_id,
        granted_at=EARLIER,
        state=state,
        revoked_at=revoked_at,
        revocation_reason=revocation_reason,
    )


class DownloadHarness:
    def __init__(self, tmp_path: Path, *, seed_cache: bool = True) -> None:
        self.store = InMemoryStore()
        self.clock = FixedClock(NOW)
        self.grants = DeliveryGrantService(secret=SECRET, lifetime_seconds=LIFETIME)
        self.cache = AssetCache(root=tmp_path, max_bytes=1024)
        if seed_cache:
            self.cache.put(DIGEST, PAYLOAD)
        self.http = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=PAYLOAD)
            )
        )
        self.delivery = DeliveryService(
            entitlements=self.store,
            entries=self.store,
            cache=self.cache,
            http=self.http,
        )
        stripe = StripeProvider(
            secret_key=SecretStr('sk_test_download_harness'),
            webhook_secret=SecretStr('whsec_download_harness'),
            http=self.http,
        )
        bepaid = BePaidProvider(
            shop_id='download-harness-shop',
            secret_key=SecretStr('bepaid_download_harness'),
            public_key_pem=BEPAID_PUBLIC_KEY_PEM,
            http=self.http,
            notification_url=BEPAID_NOTIFICATION,
        )
        checkout = CheckoutService(
            entries=self.store,
            disclosures=self.store,
            orders=self.store,
            entitlements=self.store,
            providers={'stripe': stripe, 'bepaid': bepaid},
        )
        self.client = TestClient(
            ApiApplication(
                'test',
                grants=self.grants,
                delivery=self.delivery,
                entitlements=self.store,
                clock=self.clock,
                checkout=checkout,
                disclosures=self.store,
                stripe=stripe,
                bepaid=bepaid,
                orders=self.store,
                operator_refund_key=OPERATOR_KEY,
                catalogue=build_catalogue(self.store, CATALOGUE_UNIT_AMOUNT, CATALOGUE_CURRENCY),
                preview=build_preview(self.store, self.cache, self.http),
                storefront_domain='shop.example',
            ).build()
        )


class TestDownloadRoutes:
    async def test_post_grant_entitled_buyer_gets_token(self, tmp_path: Path) -> None:
        harness = DownloadHarness(tmp_path)
        await harness.store.save_entry(build_entry())
        await harness.store.save_entitlement(build_entitlement())

        response = harness.client.post(
            f'/account/goods/{CANDIDATE_ID}/grant',
            headers={BUYER_HEADER: BUYER_ID},
        )

        assert response.status_code == 200
        body = response.json()
        assert 'token' in body
        assert body['token']
        assert 'expires_at' in body
        assert ORIGIN_URL not in response.text
        assert 'origin' not in body

    async def test_post_grant_without_entitlement_is_403(self, tmp_path: Path) -> None:
        harness = DownloadHarness(tmp_path)
        await harness.store.save_entry(build_entry())

        response = harness.client.post(
            f'/account/goods/{CANDIDATE_ID}/grant',
            headers={BUYER_HEADER: BUYER_ID},
        )

        assert response.status_code == 403
        assert 'detail' in response.json()
        assert ORIGIN_URL not in response.text

    def test_post_grant_missing_buyer_header_is_401(self, tmp_path: Path) -> None:
        harness = DownloadHarness(tmp_path)

        response = harness.client.post(f'/account/goods/{CANDIDATE_ID}/grant')

        assert response.status_code == 401
        assert 'detail' in response.json()

    async def test_get_download_valid_grant_returns_bytes(self, tmp_path: Path) -> None:
        harness = DownloadHarness(tmp_path)
        await harness.store.save_entry(build_entry())
        await harness.store.save_entitlement(build_entitlement())
        token, _grant = harness.grants.issue(BUYER_ID, CANDIDATE_ID, NOW)

        response = harness.client.get(
            f'/downloads/{token}',
            headers={BUYER_HEADER: BUYER_ID},
        )

        assert response.status_code == 200
        assert response.content == PAYLOAD
        assert response.headers['content-type'] == 'application/octet-stream'
        disposition = response.headers['content-disposition']
        assert CANDIDATE_ID in disposition or f'{CANDIDATE_ID}.bin' in disposition
        assert ORIGIN_URL not in disposition
        assert ORIGIN_URL not in response.headers.get('content-disposition', '')
        for header_value in response.headers.values():
            assert ORIGIN_URL not in header_value

    async def test_get_download_wrong_buyer_is_403(self, tmp_path: Path) -> None:
        harness = DownloadHarness(tmp_path)
        await harness.store.save_entry(build_entry())
        await harness.store.save_entitlement(build_entitlement())
        # Entitle the other buyer too so a verify that ignores buyer_id would
        # reach delivery successfully; the 403 must come from grant binding.
        await harness.store.save_entitlement(
            build_entitlement(buyer_id=OTHER_BUYER, order_id='order-other')
        )
        token, _grant = harness.grants.issue(BUYER_ID, CANDIDATE_ID, NOW)

        response = harness.client.get(
            f'/downloads/{token}',
            headers={BUYER_HEADER: OTHER_BUYER},
        )

        assert response.status_code == 403
        assert 'detail' in response.json()
        assert ORIGIN_URL not in response.text

    async def test_get_download_expired_grant_is_403(self, tmp_path: Path) -> None:
        harness = DownloadHarness(tmp_path)
        await harness.store.save_entry(build_entry())
        await harness.store.save_entitlement(build_entitlement())
        token, grant = harness.grants.issue(BUYER_ID, CANDIDATE_ID, NOW)
        harness.clock.instant = grant.expires_at

        response = harness.client.get(
            f'/downloads/{token}',
            headers={BUYER_HEADER: BUYER_ID},
        )

        assert response.status_code == 403
        body = response.json()
        assert 'detail' in body
        assert 'expired' in body['detail'].lower()
        assert ORIGIN_URL not in response.text

    async def test_get_download_revoked_entitlement_is_403_without_origin(
        self, tmp_path: Path
    ) -> None:
        harness = DownloadHarness(tmp_path)
        await harness.store.save_entry(build_entry())
        await harness.store.save_entitlement(
            build_entitlement(
                state=EntitlementState.REVOKED,
                revoked_at=EARLIER,
                revocation_reason='chargeback',
            )
        )
        token, _grant = harness.grants.issue(BUYER_ID, CANDIDATE_ID, NOW)

        response = harness.client.get(
            f'/downloads/{token}',
            headers={BUYER_HEADER: BUYER_ID},
        )

        assert response.status_code == 403
        body = response.json()
        assert 'detail' in body
        assert ORIGIN_URL not in response.text
        assert ORIGIN_URL not in body['detail']
