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
from packages.services.src.domain.category import Category, CategoryName
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.presentation import (
    CataloguePresentation,
    Locale,
    PresentationSource,
)
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
OLDEST = datetime(2026, 9, 18, 8, 0, tzinfo=UTC)
UNIT_AMOUNT = Decimal('9.99')
CURRENCY = 'USD'
OPERATOR_KEY = SecretStr('catalogue-browse-operator-key')
GRANT_SECRET = SecretStr('catalogue-browse-grant-secret')
FORBIDDEN_KEYS = ('origin_url', 'content_digest', 'storage_path')


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant


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
    names: tuple[CategoryName, ...] | None = None,
) -> Category:
    resolved_names = (
        names
        if names is not None
        else tuple(CategoryName(locale=locale, name=name) for locale in Locale)
    )
    return Category(
        category_id=category_id,
        name=name,
        slug=slug,
        saleor_category_id='saleor-cat-1',
        created_at=EARLIER,
        names=resolved_names,
    )


def build_presentation(
    title: str,
    *,
    candidate_id: str = CANDIDATE_ID,
    locale: Locale = Locale.EN,
    summary: str | None = None,
) -> CataloguePresentation:
    return CataloguePresentation(
        candidate_id=candidate_id,
        locale=locale,
        title=title,
        summary=summary if summary is not None else f'{title} summary',
        source=PresentationSource.MODEL,
        updated_at=NOW,
    )


class CatalogueHarness:
    def __init__(self, tmp_path: Path) -> None:
        self.store = InMemoryStore()
        self.cache = AssetCache(root=tmp_path, max_bytes=1024)
        self.http = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(404))
        )
        grants = DeliveryGrantService(secret=GRANT_SECRET, lifetime_seconds=900)
        delivery = DeliveryService(
            entitlements=self.store,
            entries=self.store,
            cache=self.cache,
            http=self.http,
        )
        stripe = StripeProvider(
            secret_key=SecretStr('sk_test_catalogue_browse'),
            webhook_secret=SecretStr('whsec_catalogue_browse'),
            http=self.http,
        )
        bepaid = BePaidProvider(
            shop_id='catalogue-browse-shop',
            secret_key=SecretStr('bepaid_catalogue_browse'),
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
                clock=FixedClock(NOW),
                checkout=checkout,
                disclosures=self.store,
                stripe=stripe,
                bepaid=bepaid,
                orders=self.store,
                operator_refund_key=OPERATOR_KEY,
                catalogue=build_catalogue(self.store, UNIT_AMOUNT, CURRENCY),
                preview=build_preview(self.store, self.cache, self.http),
                storefront_domain='shop.example',
            ).build()
        )

    async def stock(self, *entries: CatalogueEntry) -> None:
        for entry in entries:
            await self.store.upsert_many(
                (build_candidate(candidate_id=entry.candidate_id, title=entry.candidate_id),)
            )
            await self.store.save_entry(entry)


class TestCatalogueCategories:
    async def test_categories_are_listed_with_their_saleable_count(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.store.save_category(
            build_category(category_id='cat-audio', name='Audio', slug='audio')
        )
        await harness.stock(build_entry())

        response = harness.client.get('/catalogue/categories')

        assert response.status_code == 200
        assert response.json() == [
            {'category_id': 'cat-audio', 'name': 'Audio', 'slug': 'audio', 'count': 0},
            {'category_id': 'cat-images', 'name': 'Images', 'slug': 'images', 'count': 1},
        ]

    async def test_a_category_counts_only_goods_a_buyer_can_buy(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.stock(
            build_entry(),
            build_entry(
                candidate_id=OTHER_ID,
                category_id='cat-images',
                listing=StorefrontListing.FREE_ONLY,
            ),
        )

        response = harness.client.get('/catalogue/categories')

        assert response.json() == [
            {'category_id': 'cat-images', 'name': 'Images', 'slug': 'images', 'count': 1}
        ]

    async def test_a_locale_is_accepted_and_an_unknown_one_is_422(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)

        assert harness.client.get('/catalogue/categories', params={'locale': 'be'}).status_code == 200
        assert harness.client.get('/catalogue/categories', params={'locale': 'de'}).status_code == 422

    async def test_each_locale_reads_the_name_stored_for_it(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(
            build_category(
                names=(
                    CategoryName(locale=Locale.RU, name='Изображения'),
                    CategoryName(locale=Locale.BE, name='Выявы'),
                    CategoryName(locale=Locale.EN, name='Images'),
                )
            )
        )

        english = harness.client.get(
            '/catalogue/categories', params={'locale': 'en'}
        ).json()
        russian = harness.client.get(
            '/catalogue/categories', params={'locale': 'ru'}
        ).json()
        belarusian = harness.client.get(
            '/catalogue/categories', params={'locale': 'be'}
        ).json()

        assert [row['name'] for row in english] == ['Images']
        assert [row['name'] for row in russian] == ['Изображения']
        assert [row['name'] for row in belarusian] == ['Выявы']


class TestCatalogueCategoryPage:
    async def test_a_category_page_carries_its_summary_and_its_items(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.stock(build_entry())

        response = harness.client.get('/catalogue/categories/images')

        assert response.status_code == 200
        body = response.json()
        assert body['category_id'] == 'cat-images'
        assert body['slug'] == 'images'
        assert body['count'] == 1
        assert body['total'] == 1
        assert [item['candidate_id'] for item in body['items']] == [CANDIDATE_ID]

    async def test_a_category_page_holds_only_the_goods_of_its_category(
        self, tmp_path: Path
    ) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.store.save_category(
            build_category(category_id='cat-audio', name='Audio', slug='audio')
        )
        await harness.stock(
            build_entry(),
            build_entry(candidate_id=OTHER_ID, category_id='cat-audio'),
        )

        response = harness.client.get('/catalogue/categories/audio')

        assert [item['candidate_id'] for item in response.json()['items']] == [OTHER_ID]

    async def test_an_unknown_category_slug_is_404(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)

        response = harness.client.get('/catalogue/categories/missing')

        assert response.status_code == 404

    async def test_an_empty_category_is_200_with_no_items(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())

        response = harness.client.get('/catalogue/categories/images')

        assert response.status_code == 200
        body = response.json()
        assert body['items'] == []
        assert body['total'] == 0


class TestCatalogueGoods:
    async def test_list_goods_filters_non_saleable(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(category_id=None),
            build_entry(
                candidate_id=OTHER_ID,
                category_id=None,
                listing=StorefrontListing.FREE_ONLY,
            ),
        )

        response = harness.client.get('/catalogue/goods')

        assert response.status_code == 200
        body = response.json()
        assert [item['candidate_id'] for item in body['items']] == [CANDIDATE_ID]
        assert body['total'] == 1
        assert body['limit'] == 24
        assert body['offset'] == 0
        assert ORIGIN_URL not in response.text

    async def test_the_total_counts_every_match_not_the_page(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(),
            build_entry(candidate_id=OTHER_ID, category_id=None),
            build_entry(candidate_id='openverse:3', category_id=None),
        )

        response = harness.client.get('/catalogue/goods', params={'limit': 2})

        body = response.json()
        assert len(body['items']) == 2
        assert body['total'] == 3
        assert body['limit'] == 2

    async def test_the_offset_walks_the_matches(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(published_at=NOW),
            build_entry(
                candidate_id=OTHER_ID, category_id=None, published_at=EARLIER
            ),
        )

        response = harness.client.get('/catalogue/goods', params={'offset': 1})

        body = response.json()
        assert [item['candidate_id'] for item in body['items']] == [OTHER_ID]
        assert body['offset'] == 1
        assert body['total'] == 2

    async def test_newest_is_the_default_order(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(published_at=OLDEST),
            build_entry(candidate_id=OTHER_ID, category_id=None, published_at=EARLIER),
        )

        response = harness.client.get('/catalogue/goods')

        assert [item['candidate_id'] for item in response.json()['items']] == [
            OTHER_ID,
            CANDIDATE_ID,
        ]

    async def test_title_asc_orders_by_the_resolved_title(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(published_at=OLDEST),
            build_entry(candidate_id=OTHER_ID, category_id=None, published_at=EARLIER),
        )
        await harness.store.save_presentation(
            build_presentation('Alpha', locale=Locale.EN)
        )
        await harness.store.save_presentation(
            build_presentation('Zulu', candidate_id=OTHER_ID, locale=Locale.EN)
        )

        response = harness.client.get(
            '/catalogue/goods', params={'sort': 'title_asc', 'locale': 'en'}
        )

        assert [item['candidate_id'] for item in response.json()['items']] == [
            CANDIDATE_ID,
            OTHER_ID,
        ]

    async def test_title_desc_reverses_the_title_order(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(published_at=OLDEST),
            build_entry(candidate_id=OTHER_ID, category_id=None, published_at=EARLIER),
        )
        await harness.store.save_presentation(build_presentation('Alpha', locale=Locale.EN))
        await harness.store.save_presentation(
            build_presentation('Zulu', candidate_id=OTHER_ID, locale=Locale.EN)
        )

        response = harness.client.get(
            '/catalogue/goods', params={'sort': 'title_desc', 'locale': 'en'}
        )

        assert [item['candidate_id'] for item in response.json()['items']] == [
            OTHER_ID,
            CANDIDATE_ID,
        ]

    async def test_an_unrecognised_sort_is_422(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)

        response = harness.client.get('/catalogue/goods', params={'sort': 'cheapest'})

        assert response.status_code == 422

    async def test_a_limit_outside_the_contract_is_422(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)

        assert harness.client.get('/catalogue/goods', params={'limit': 0}).status_code == 422
        assert harness.client.get('/catalogue/goods', params={'limit': 61}).status_code == 422

    async def test_a_negative_offset_is_422(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)

        response = harness.client.get('/catalogue/goods', params={'offset': -1})

        assert response.status_code == 422

    async def test_a_search_term_matches_the_localised_title(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(build_entry(), build_entry(candidate_id=OTHER_ID, category_id=None))
        await harness.store.save_presentation(build_presentation('Midnight Harbour'))
        await harness.store.save_presentation(
            build_presentation('Morning Field', candidate_id=OTHER_ID)
        )

        response = harness.client.get(
            '/catalogue/goods', params={'q': 'harbour', 'locale': 'en'}
        )

        body = response.json()
        assert [item['candidate_id'] for item in body['items']] == [CANDIDATE_ID]
        assert body['total'] == 1

    async def test_a_search_term_matches_the_source_title(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.upsert_many(
            (
                build_candidate(candidate_id=CANDIDATE_ID, title='DSC_0421.png'),
                build_candidate(candidate_id=OTHER_ID, title='photo_of_a_bridge.jpg'),
            )
        )
        await harness.store.save_entry(build_entry(category_id=None))
        await harness.store.save_entry(build_entry(candidate_id=OTHER_ID, category_id=None))

        response = harness.client.get('/catalogue/goods', params={'q': 'bridge'})

        assert [item['candidate_id'] for item in response.json()['items']] == [OTHER_ID]

    async def test_a_search_term_matches_the_creator(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.upsert_many(
            (
                build_candidate(candidate_id=CANDIDATE_ID, title='DSC_0421.png'),
                build_candidate(candidate_id=OTHER_ID, title='DSC_0422.png'),
            )
        )
        await harness.store.save_entry(build_entry(category_id=None))
        await harness.store.save_entry(build_entry(candidate_id=OTHER_ID, category_id=None))

        response = harness.client.get('/catalogue/goods', params={'q': 'example author'})

        assert len(response.json()['items']) == 2

    async def test_a_search_term_that_matches_nothing_is_an_empty_page(
        self, tmp_path: Path
    ) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(build_entry())

        response = harness.client.get('/catalogue/goods', params={'q': 'nothing-like-this'})

        body = response.json()
        assert body['items'] == []
        assert body['total'] == 0

    async def test_a_license_filter_selects_only_that_license(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(license_id='CC-BY-4.0'),
            build_entry(candidate_id=OTHER_ID, category_id=None, license_id='CC0-1.0'),
        )

        response = harness.client.get('/catalogue/goods', params={'license': 'CC0-1.0'})

        assert [item['candidate_id'] for item in response.json()['items']] == [OTHER_ID]

    async def test_a_category_filter_selects_only_that_category(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.store.save_category(
            build_category(category_id='cat-audio', name='Audio', slug='audio')
        )
        await harness.stock(
            build_entry(category_id='cat-images'),
            build_entry(candidate_id=OTHER_ID, category_id='cat-audio'),
        )

        response = harness.client.get('/catalogue/goods', params={'category': 'audio'})

        assert [item['candidate_id'] for item in response.json()['items']] == [OTHER_ID]

    async def test_an_unknown_category_filter_matches_nothing(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(build_entry())

        response = harness.client.get('/catalogue/goods', params={'category': 'missing'})

        body = response.json()
        assert body['items'] == []
        assert body['total'] == 0


class TestCatalogueCard:
    async def test_a_card_carries_what_a_buyer_reads(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.store.save_category(build_category())
        await harness.stock(build_entry(obligations=()))

        response = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}')

        assert response.status_code == 200
        body = response.json()
        assert body['candidate_id'] == CANDIDATE_ID
        assert body['title'] == CANDIDATE_ID
        assert body['original_title'] == CANDIDATE_ID
        assert body['summary'] is None
        assert body['creator'] == 'Example Author'
        assert body['license_id'] == 'CC-BY-4.0'
        assert body['obligations'] == []
        assert body['category_id'] == 'cat-images'
        assert body['category_slug'] == 'images'
        assert body['unit_amount'] == '9.99'
        assert body['currency'] == 'USD'
        assert body['content_type'] == 'image'
        assert body['size_bytes'] == 1024
        assert body['published_at'] == '2026-09-19T08:00:00Z'

    async def test_a_card_names_no_origin_digest_or_path(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(build_entry())

        response = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}')

        body = response.json()
        for key in FORBIDDEN_KEYS:
            assert key not in body
        assert ORIGIN_URL not in response.text
        assert DIGEST not in response.text
        assert 'landing_url' not in body
        assert 'download_url' not in body

    async def test_a_card_points_at_the_preview_route_and_says_whether_it_is_a_cover(
        self, tmp_path: Path
    ) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(build_entry())

        body = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}').json()

        assert body['preview_url'] == f'/catalogue/goods/{CANDIDATE_ID}/preview'
        assert body['preview_is_cover'] is False

    async def test_a_card_of_a_curated_good_carries_the_localised_copy(
        self, tmp_path: Path
    ) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(build_entry())
        await harness.store.save_presentation(
            build_presentation('Midnight Harbour', locale=Locale.BE, summary='Ночная гавань')
        )

        body = harness.client.get(
            f'/catalogue/goods/{CANDIDATE_ID}', params={'locale': 'be'}
        ).json()

        assert body['title'] == 'Midnight Harbour'
        assert body['summary'] == 'Ночная гавань'
        assert body['original_title'] == CANDIDATE_ID

    async def test_a_good_with_no_copy_for_the_locale_falls_back_to_russian(
        self, tmp_path: Path
    ) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(build_entry())
        await harness.store.save_presentation(
            build_presentation('Полночная гавань', locale=Locale.RU)
        )

        body = harness.client.get(
            f'/catalogue/goods/{CANDIDATE_ID}', params={'locale': 'en'}
        ).json()

        assert body['title'] == 'Полночная гавань'

    async def test_withdrawn_good_is_404(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(state=CatalogueEntryState.WITHDRAWN, category_id=None)
        )

        response = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}')

        assert response.status_code == 404
        assert 'origin_url' not in response.text
        assert ORIGIN_URL not in response.text

    async def test_free_only_good_is_404(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)
        await harness.stock(
            build_entry(listing=StorefrontListing.FREE_ONLY, category_id=None)
        )

        response = harness.client.get(f'/catalogue/goods/{CANDIDATE_ID}')

        assert response.status_code == 404

    async def test_unknown_good_is_404(self, tmp_path: Path) -> None:
        harness = CatalogueHarness(tmp_path)

        response = harness.client.get('/catalogue/goods/missing')

        assert response.status_code == 404
