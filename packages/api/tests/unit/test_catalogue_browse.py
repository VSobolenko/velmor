from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from packages.api.src.app import ApiApplication
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.category import Category
from packages.services.src.domain.license import StorefrontListing
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
DIGEST = hashlib.sha256(b'catalogue-browse-bytes').hexdigest()
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
EARLIER = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)
UNIT_AMOUNT = Decimal('9.99')
CURRENCY = 'BYN'
OPERATOR_KEY = SecretStr('catalogue-browse-operator-key')
GRANT_SECRET = SecretStr('catalogue-browse-grant-secret')


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant


class _StaticCatalog:
    async def published(self, limit: int) -> tuple:
        return ()

    async def published_count(self) -> int:
        return 0


def build_entry(
    *,
    candidate_id: str = CANDIDATE_ID,
    category_id: str | None = 'cat-images',
    listing: StorefrontListing = StorefrontListing.PAID_OK,
    state: CatalogueEntryState = CatalogueEntryState.PUBLISHED,
    obligations: tuple[str, ...] = ('Credit the creator',),
    license_id: str | None = 'CC-BY-4.0',
    published_at: datetime = EARLIER,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=category_id,
        license_id=license_id,
        obligations=obligations,
        listing=listing,
        state=state,
        withdrawal_reason='withdrawn for test' if state is CatalogueEntryState.WITHDRAWN else None,
        published_at=published_at,
        content_digest=DIGEST,
        origin_url=ORIGIN_URL,
    )


def build_category(
    *,
    category_id: str = 'cat-images',
    name: str = 'Images',
    slug: str = 'images',
) -> Category:
    return Category(
        category_id=category_id,
        name=name,
        slug=slug,
        saleor_category_id='saleor-cat-1',
        created_at=EARLIER,
    )


class CatalogueHarness:
    def __init__(self, tmp_path: Path) -> None:
        self.store = InMemoryStore()
        http = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(404))
        )
        grants = DeliveryGrantService(secret=GRANT_SECRET, lifetime_seconds=900)
        cache = AssetCache(root=tmp_path, max_bytes=1024)
        delivery = DeliveryService(
            entitlements=self.store,
            entries=self.store,
            cache=cache,
            http=http,
        )
        stripe = StripeProvider(
            secret_key=SecretStr('sk_test_catalogue_browse'),
            webhook_secret=SecretStr('whsec_catalogue_browse'),
            http=http,
        )
        bepaid = BePaidProvider(
            shop_id='catalogue-browse-shop',
            secret_key=SecretStr('bepaid_catalogue_browse'),
            public_key_pem=BEPAID_PUBLIC_KEY_PEM,
            http=http,
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
                _StaticCatalog(),
                grants=grants,
                delivery=delivery,
                entitlements=self.store,
                clock=FixedClock(NOW),
                checkout=checkout,
                disclosures=self.store,
                stripe=stripe,
                bepaid=bepaid,
                orders=self.store,
                operator_refund_key=OPERATOR_KEY,
                entries=self.store,
                categories=self.store,
                candidates=self.store,
                catalogue_unit_amount=UNIT_AMOUNT,
                catalogue_currency=CURRENCY,
                storefront_domain='shop.example',
            ).build()
        )


class TestCatalogueBrowse:
    async def test_list_categories(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.store.save_category(
            build_category(category_id='cat-audio', name='Audio', slug='audio')
        )

        response = harness.client.get('/catalogue/categories')

        assert response.status_code == 200
        body = response.json()
        assert body == [
            {'category_id': 'cat-audio', 'name': 'Audio', 'slug': 'audio'},
            {'category_id': 'cat-images', 'name': 'Images', 'slug': 'images'},
        ]

    async def test_category_by_slug_lists_saleable_goods(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.store.upsert_many(
            (build_candidate(candidate_id=CANDIDATE_ID, title='Saleable photo'),)
        )
        await harness.store.save_entry(build_entry())

        response = harness.client.get('/catalogue/categories/images')

        assert response.status_code == 200
        body = response.json()
        assert body['category_id'] == 'cat-images'
        assert body['slug'] == 'images'
        assert len(body['goods']) == 1
        good = body['goods'][0]
        assert good['candidate_id'] == CANDIDATE_ID
        assert good['title'] == 'Saleable photo'
        assert good['license_id'] == 'CC-BY-4.0'
        assert good['obligations'] == ['Credit the creator']
        assert good['unit_amount'] == '9.99'
        assert good['currency'] == 'BYN'
        assert 'origin_url' not in good
        assert 'content_digest' not in good
        assert 'landing_url' not in good

    async def test_unknown_category_slug_is_404(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)

        response = harness.client.get('/catalogue/categories/missing')

        assert response.status_code == 404

    async def test_empty_category_is_200_with_empty_goods(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())

        response = harness.client.get('/catalogue/categories/images')

        assert response.status_code == 200
        body = response.json()
        assert body['goods'] == []

    async def test_list_goods_filters_non_saleable(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.upsert_many(
            (
                build_candidate(candidate_id=CANDIDATE_ID, title='Paid'),
                build_candidate(candidate_id=OTHER_ID, title='Free only'),
            )
        )
        await harness.store.save_entry(
            build_entry(published_at=NOW, category_id=None)
        )
        await harness.store.save_entry(
            build_entry(
                candidate_id=OTHER_ID,
                listing=StorefrontListing.FREE_ONLY,
                published_at=EARLIER,
                category_id=None,
            )
        )

        response = harness.client.get('/catalogue/goods')

        assert response.status_code == 200
        body = response.json()
        assert [item['candidate_id'] for item in body] == [CANDIDATE_ID]
        assert ORIGIN_URL not in response.text

    async def test_get_good_happy_path(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.store.upsert_many(
            (build_candidate(candidate_id=CANDIDATE_ID, title='Leaf'),)
        )
        await harness.store.save_entry(build_entry(obligations=()))

        response = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}')

        assert response.status_code == 200
        body = response.json()
        assert body['title'] == 'Leaf'
        assert body['creator'] == 'Example Author'
        assert body['license_id'] == 'CC-BY-4.0'
        assert body['obligations'] == []
        assert body['category_id'] == 'cat-images'
        assert body['category_slug'] == 'images'
        assert body['unit_amount'] == '9.99'
        assert body['currency'] == 'BYN'
        assert 'origin_url' not in body

    async def test_withdrawn_good_is_404(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await harness.store.save_entry(
            build_entry(state=CatalogueEntryState.WITHDRAWN, category_id=None)
        )

        response = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}')

        assert response.status_code == 404
        assert 'origin_url' not in response.text
        assert ORIGIN_URL not in response.text

    async def test_free_only_good_is_404(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await harness.store.save_entry(
            build_entry(listing=StorefrontListing.FREE_ONLY, category_id=None)
        )

        response = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}')

        assert response.status_code == 404

    async def test_unknown_good_is_404(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)

        response = harness.client.get('/catalogue/goods/missing')

        assert response.status_code == 404
