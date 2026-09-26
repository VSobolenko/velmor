from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image
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
from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.preview import CatalogueCover, CoverSource
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.stripe_provider import StripeProvider
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate
from packages.services.tests.unit.payments.test_bepaid_provider import (
    PUBLIC_KEY_PEM as BEPAID_PUBLIC_KEY_PEM,
)

ORIGIN_URL = 'https://secret-origin.example/never-leak/asset.bin'
CANDIDATE_ID = 'openverse:1'
OTHER_ID = 'openverse:2'
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
UNIT_AMOUNT = Decimal('9.99')
CURRENCY = 'USD'
OPERATOR_KEY = SecretStr('catalogue-preview-operator-key')
GRANT_SECRET = SecretStr('catalogue-preview-grant-secret')
CACHE_MAX_BYTES = 8_000_000


def build_image(width: int, height: int, colour: str) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), colour).save(buffer, format='PNG')
    return buffer.getvalue()


def build_entry(
    body: bytes,
    *,
    candidate_id: str = CANDIDATE_ID,
    listing: StorefrontListing = StorefrontListing.PAID_OK,
    state: CatalogueEntryState = CatalogueEntryState.PUBLISHED,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=(),
        listing=listing,
        state=state,
        withdrawal_reason='withdrawn for test' if state is CatalogueEntryState.WITHDRAWN else None,
        published_at=NOW,
        content_digest=hashlib.sha256(body).hexdigest(),
        origin_url=ORIGIN_URL,
    )


class PreviewHarness:
    """An API whose origin serves one prepared body, or fails to."""

    def __init__(
        self,
        tmp_path: Path,
        body: bytes,
        *,
        status: int = 200,
        unreachable: bool = False,
    ) -> None:
        self.store = InMemoryStore()
        self.cache = AssetCache(root=tmp_path, max_bytes=CACHE_MAX_BYTES)
        self.body = body

        def handler(request: httpx.Request) -> httpx.Response:
            if unreachable:
                raise httpx.ConnectError('connection refused', request=request)
            return httpx.Response(status, content=body)

        self.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        grants = DeliveryGrantService(secret=GRANT_SECRET, lifetime_seconds=900)
        accounts = build_accounts(self.store, lambda: NOW)
        delivery = DeliveryService(
            entitlements=self.store,
            entries=self.store,
            cache=self.cache,
            http=self.http,
        )
        stripe = StripeProvider(
            secret_key=SecretStr('sk_test_catalogue_preview'),
            webhook_secret=SecretStr('whsec_catalogue_preview'),
            http=self.http,
        )
        bepaid = BePaidProvider(
            shop_id='catalogue-preview-shop',
            secret_key=SecretStr('bepaid_catalogue_preview'),
            public_key_pem=BEPAID_PUBLIC_KEY_PEM,
            http=self.http,
            notification_url='https://shop.example/webhooks/bepaid',
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
                grants=grants,
                delivery=delivery,
                entitlements=self.store,
                clock=lambda: NOW,
                checkout=checkout,
                disclosures=self.store,
                stripe=stripe,
                bepaid=bepaid,
                orders=self.store,
                operator_refund_key=OPERATOR_KEY,
                catalogue=build_catalogue(self.store, UNIT_AMOUNT, CURRENCY),
                preview=build_preview(self.store, self.cache, self.http),
                storefront_domain='shop.example',
                accounts=accounts,
                session_cookie_name=TEST_SESSION_COOKIE_NAME,
                session_lifetime_seconds=TEST_SESSION_LIFETIME_SECONDS,
                password_min_length=TEST_PASSWORD_MIN_LENGTH,
            ).build()
        )

    async def stock(self, entry: CatalogueEntry) -> None:
        await self.store.upsert_many((build_candidate(candidate_id=entry.candidate_id),))
        await self.store.save_entry(entry)

    async def attach_cover(self, cover_body: bytes, *, candidate_id: str = CANDIDATE_ID) -> str:
        digest = hashlib.sha256(cover_body).hexdigest()
        PreviewDerivative(self.cache).cut(digest, cover_body)
        await self.store.save_cover(
            CatalogueCover(
                candidate_id=candidate_id,
                digest=digest,
                media_type=PreviewDerivative(self.cache).media_type,
                source=CoverSource.GENERATED,
                rights_note='generated for this good by the operator',
                attached_at=NOW,
            )
        )
        return digest

    def get(self, candidate_id: str = CANDIDATE_ID) -> httpx.Response:
        return self.client.get(f'/catalogue/goods/{candidate_id}/preview')


class TestPreviewServed:
    async def test_a_published_good_is_served_as_a_bounded_image(self, tmp_path: Path) -> None:
        harness = PreviewHarness(tmp_path, build_image(2400, 1200, 'navy'))
        await harness.stock(build_entry(harness.body))

        response = harness.get()

        assert response.status_code == 200
        assert response.headers['content-type'] in ('image/webp', 'image/jpeg')
        with Image.open(io.BytesIO(response.content)) as rendered:
            assert max(rendered.size) == PreviewDerivative.MAX_EDGE

    async def test_the_response_is_cacheable_and_etagged_by_the_digest(
        self, tmp_path: Path
    ) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'))
        entry = build_entry(harness.body)
        await harness.stock(entry)

        response = harness.get()

        assert response.headers['etag'] == f'"{entry.content_digest}"'
        assert (
            response.headers['cache-control']
            == ApiApplication.PREVIEW_CACHE_CONTROL
            == 'public, max-age=31536000, immutable'
        )

    async def test_the_origin_url_appears_in_no_response(self, tmp_path: Path) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'))
        await harness.stock(build_entry(harness.body))

        response = harness.get()

        assert ORIGIN_URL not in response.text
        assert ORIGIN_URL not in str(dict(response.headers))

    async def test_a_stored_cover_is_served_in_place_of_the_origin(
        self, tmp_path: Path
    ) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'))
        await harness.stock(build_entry(harness.body))
        cover_digest = await harness.attach_cover(build_image(600, 600, 'crimson'))

        response = harness.get()
        card = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}')

        assert response.status_code == 200
        assert response.headers['etag'] == f'"{cover_digest}"'
        assert card.json()['preview_is_cover'] is True

    async def test_an_image_already_in_the_cache_is_served_without_the_origin(
        self, tmp_path: Path
    ) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'), unreachable=True)
        entry = build_entry(build_image(400, 300, 'navy'))
        await harness.stock(entry)
        digest = entry.content_digest

        PreviewDerivative(harness.cache).cut(digest, build_image(400, 300, 'navy'))
        response = harness.get()

        assert response.status_code == 200
        assert response.headers['etag'] == f'"{digest}"'


class TestPreviewRefusals:
    async def test_an_unknown_good_is_404(self, tmp_path: Path) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'))

        response = harness.get()

        assert response.status_code == 404

    async def test_a_withdrawn_good_is_404(self, tmp_path: Path) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'))
        await harness.stock(
            build_entry(harness.body, state=CatalogueEntryState.WITHDRAWN)
        )

        response = harness.get()

        assert response.status_code == 404
        assert ORIGIN_URL not in response.text

    async def test_a_free_only_good_is_404(self, tmp_path: Path) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'))
        await harness.stock(build_entry(harness.body, listing=StorefrontListing.FREE_ONLY))

        assert harness.get().status_code == 404

    async def test_a_payload_that_is_not_an_image_is_502(self, tmp_path: Path) -> None:
        harness = PreviewHarness(tmp_path, b'this is not an image')
        await harness.stock(build_entry(harness.body))

        response = harness.get()

        assert response.status_code == 502
        assert ORIGIN_URL not in response.text

    async def test_a_refused_payload_is_distinguishable_from_an_absent_good(
        self, tmp_path: Path
    ) -> None:
        absent = PreviewHarness(tmp_path / 'absent', build_image(400, 300, 'navy'))
        unrenderable = PreviewHarness(tmp_path / 'unrenderable', b'this is not an image')
        await unrenderable.stock(build_entry(unrenderable.body))

        assert absent.get().status_code == 404
        assert unrenderable.get().status_code == 502

    async def test_the_refusal_bodies_are_fixed_and_name_no_origin(
        self, tmp_path: Path
    ) -> None:
        absent = PreviewHarness(tmp_path / 'absent', build_image(400, 300, 'navy'))
        unrenderable = PreviewHarness(tmp_path / 'unrenderable', b'this is not an image')
        await unrenderable.stock(build_entry(unrenderable.body))

        absent_response = absent.get()
        refused_response = unrenderable.get()

        assert absent_response.json() == {'detail': 'no preview exists for this good'}
        assert refused_response.json() == {'detail': 'the preview could not be produced'}
        assert ORIGIN_URL not in absent_response.text
        assert ORIGIN_URL not in refused_response.text

    async def test_origin_bytes_that_moved_are_409(self, tmp_path: Path) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'crimson'))
        await harness.stock(build_entry(build_image(400, 300, 'navy')))

        response = harness.get()

        assert response.status_code == 409
        assert ORIGIN_URL not in response.text

    async def test_an_unreachable_origin_is_502(self, tmp_path: Path) -> None:
        harness = PreviewHarness(
            tmp_path, build_image(400, 300, 'navy'), unreachable=True
        )
        await harness.stock(build_entry(harness.body))

        response = harness.get()

        assert response.status_code == 502
        assert ORIGIN_URL not in response.text

    async def test_an_origin_error_status_is_502(self, tmp_path: Path) -> None:
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'), status=503)
        await harness.stock(build_entry(harness.body))

        response = harness.get()

        assert response.status_code == 502
        assert ORIGIN_URL not in response.text

    async def test_a_cover_whose_bytes_are_gone_is_500(self, tmp_path: Path) -> None:
        """Our own inconsistent state, not an upstream failure.

        The cover row exists and its bytes are absent from our cache, which only
        we can cause. 502 would name an upstream failure that did not happen and
        send an operator to inspect an origin that is fine, so the contract fixes
        500 (contract.md); re-running "velmor cover" repairs it. The body names no
        origin either way, which is the part that matters to a buyer.
        """
        harness = PreviewHarness(tmp_path, build_image(400, 300, 'navy'))
        await harness.stock(build_entry(harness.body))
        await harness.store.save_cover(
            CatalogueCover(
                candidate_id=CANDIDATE_ID,
                digest='f' * 64,
                media_type=PreviewDerivative(harness.cache).media_type,
                source=CoverSource.GENERATED,
                rights_note='generated for this good by the operator',
                attached_at=NOW,
            )
        )

        response = harness.get()

        assert response.status_code == 500
        assert ORIGIN_URL not in response.text
        assert ORIGIN_URL not in str(dict(response.headers))
