from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.services.src.commerce.catalogue_service import StorefrontCatalogue
from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.domain.catalogue import (
    CatalogueEntry,
    CatalogueEntryState,
    SaleableEntry,
)
from packages.services.src.domain.catalogue_card import CatalogueCard
from packages.services.src.domain.catalogue_query import CatalogueSort
from packages.services.src.domain.category import Category, CategoryName
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.presentation import (
    CataloguePresentation,
    Locale,
    PresentationSource,
)
from packages.services.src.domain.preview import CatalogueCover, CoverSource
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
EARLIER = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)
OLDEST = datetime(2026, 9, 18, 8, 0, tzinfo=UTC)
DIGEST = 'a' * 64
ORIGIN_URL = 'https://secret-origin.example/never-leak/asset.bin'
UNIT_AMOUNT = Decimal('9.99')
CURRENCY = 'BYN'

FORBIDDEN_KEYS = ('origin_url', 'content_digest', 'landing_url', 'storage_path', 'download_url')


def build_entry(
    candidate_id: str = 'openverse:1',
    category_id: str | None = None,
    license_id: str | None = 'CC-BY-4.0',
    listing: StorefrontListing = StorefrontListing.PAID_OK,
    state: CatalogueEntryState = CatalogueEntryState.PUBLISHED,
    published_at: datetime = EARLIER,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id=f'product-{candidate_id}',
        saleor_variant_id=f'variant-{candidate_id}',
        category_id=category_id,
        license_id=license_id,
        obligations=('Credit the creator',),
        listing=listing,
        state=state,
        withdrawal_reason='withdrawn for test' if state is CatalogueEntryState.WITHDRAWN else None,
        published_at=published_at,
        content_digest=DIGEST,
        origin_url=ORIGIN_URL,
    )


def build_category(
    category_id: str = 'cat-photography',
    name: str = 'Photography',
    slug: str = 'photography',
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
        saleor_category_id=f'saleor-{category_id}',
        created_at=EARLIER,
        names=resolved_names,
    )


def build_presentation(
    candidate_id: str = 'openverse:1',
    locale: Locale = Locale.EN,
    title: str = 'English title',
    summary: str = 'English summary',
) -> CataloguePresentation:
    return CataloguePresentation(
        candidate_id=candidate_id,
        locale=locale,
        title=title,
        summary=summary,
        source=PresentationSource.OPERATOR,
        updated_at=NOW,
    )


def build_cover(candidate_id: str = 'openverse:1') -> CatalogueCover:
    return CatalogueCover(
        candidate_id=candidate_id,
        digest='b' * 64,
        media_type='image/webp',
        source=CoverSource.GENERATED,
        rights_note='generated for this good',
        attached_at=NOW,
    )


async def save_good(
    store: InMemoryStore,
    candidate_id: str = 'openverse:1',
    title: str = 'Sample good',
    **overrides: object,
) -> CatalogueEntry:
    """Store the candidate row and the catalogue entry a card is built from.

    Both are needed: the card takes its licence, obligations and publication time
    from the entry, and its creator, format and size from the candidate.
    """
    entry = build_entry(candidate_id, **overrides)
    await store.upsert_many((build_candidate(candidate_id=candidate_id, title=title),))
    await store.save_entry(entry)
    return entry


def build_catalogue(store: InMemoryStore) -> StorefrontCatalogue:
    return StorefrontCatalogue(
        catalog=store,
        entries=store,
        categories=store,
        candidates=store,
        covers=store,
        presentations=PresentationService(store),
        unit_amount=UNIT_AMOUNT,
        currency=CURRENCY,
    )


class TestCataloguePage:
    async def test_matches_are_ordered_newest_first_by_default(self) -> None:
        store = InMemoryStore()
        await save_good(store, 'openverse:1', published_at=OLDEST)
        await save_good(store, 'openverse:2', published_at=NOW)
        await save_good(store, 'openverse:3', published_at=EARLIER)

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0
        )

        assert tuple(card.candidate_id for card in page.items) == (
            'openverse:2',
            'openverse:3',
            'openverse:1',
        )

    async def test_goods_sharing_a_timestamp_are_ordered_deterministically(self) -> None:
        store = InMemoryStore()
        await save_good(store, 'openverse:b')
        await save_good(store, 'openverse:a')
        catalogue = build_catalogue(store)

        first = await catalogue.page(Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0)
        second = await catalogue.page(Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0)

        assert tuple(card.candidate_id for card in first.items) == (
            'openverse:a',
            'openverse:b',
        )
        assert first == second

    async def test_price_orders_agree_while_the_price_is_flat(self) -> None:
        """Per-good pricing does not exist yet, so a price order cannot differ.

        ``CATALOGUE_UNIT_AMOUNT`` is one value for the whole catalogue (design:
        "No per-good pricing"), so both directions fall back to the tie-break on
        candidate id. The test states that rather than pretending the order means
        something, and it will fail the day a real price is introduced and the two
        orders should diverge.
        """
        store = InMemoryStore()
        for candidate_id in ('openverse:1', 'openverse:2', 'openverse:3'):
            await save_good(store, candidate_id)
        catalogue = build_catalogue(store)

        ascending = await catalogue.page(
            Locale.RU, CatalogueSort.PRICE_ASC, None, None, None, 24, 0
        )
        descending = await catalogue.page(
            Locale.RU, CatalogueSort.PRICE_DESC, None, None, None, 24, 0
        )

        expected = ('openverse:1', 'openverse:2', 'openverse:3')
        assert tuple(card.candidate_id for card in ascending.items) == expected
        assert tuple(card.candidate_id for card in descending.items) == expected
        assert {card.unit_amount for card in ascending.items} == {'9.99'}

    async def test_titles_are_ordered_over_the_resolved_title(self) -> None:
        store = InMemoryStore()
        for candidate_id, title in (
            ('openverse:1', 'banana'),
            ('openverse:2', 'Apple'),
            ('openverse:3', 'cherry'),
        ):
            await save_good(store, candidate_id)
            await store.save_presentation(build_presentation(candidate_id, title=title))

        page = await build_catalogue(store).page(
            Locale.EN, CatalogueSort.TITLE_ASC, None, None, None, 24, 0
        )

        assert tuple(card.title for card in page.items) == ('Apple', 'banana', 'cherry')

    async def test_the_title_order_is_reversed_for_descending(self) -> None:
        store = InMemoryStore()
        for candidate_id, title in (('openverse:1', 'banana'), ('openverse:2', 'Apple')):
            await save_good(store, candidate_id)
            await store.save_presentation(build_presentation(candidate_id, title=title))

        page = await build_catalogue(store).page(
            Locale.EN, CatalogueSort.TITLE_DESC, None, None, None, 24, 0
        )

        assert tuple(card.title for card in page.items) == ('banana', 'Apple')

    async def test_the_total_counts_every_match_not_the_page(self) -> None:
        store = InMemoryStore()
        for index in range(5):
            await save_good(store, f'openverse:{index}')

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 2, 0
        )

        assert len(page.items) == 2
        assert page.total == 5
        assert page.limit == 2
        assert page.offset == 0

    async def test_an_offset_walks_the_ordered_catalogue(self) -> None:
        store = InMemoryStore()
        for index in range(4):
            await save_good(
                store, f'openverse:{index}', published_at=EARLIER + timedelta(hours=index)
            )
        catalogue = build_catalogue(store)

        first = await catalogue.page(Locale.RU, CatalogueSort.NEWEST, None, None, None, 2, 0)
        second = await catalogue.page(Locale.RU, CatalogueSort.NEWEST, None, None, None, 2, 2)

        assert tuple(card.candidate_id for card in first.items) == (
            'openverse:3',
            'openverse:2',
        )
        assert tuple(card.candidate_id for card in second.items) == (
            'openverse:1',
            'openverse:0',
        )
        assert second.total == 4

    async def test_an_offset_past_the_end_is_an_empty_page(self) -> None:
        store = InMemoryStore()
        await save_good(store)

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 10
        )

        assert page.items == ()
        assert page.total == 1

    async def test_a_withdrawn_good_is_in_no_page(self) -> None:
        store = InMemoryStore()
        await save_good(store, 'openverse:1')
        await save_good(store, 'openverse:2', state=CatalogueEntryState.WITHDRAWN)

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0
        )

        assert tuple(card.candidate_id for card in page.items) == ('openverse:1',)
        assert page.total == 1

    async def test_a_free_only_good_is_in_no_page(self) -> None:
        store = InMemoryStore()
        await save_good(store, 'openverse:1', listing=StorefrontListing.FREE_ONLY)

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0
        )

        assert page.items == ()
        assert page.total == 0


class TestSearch:
    async def test_a_term_matches_the_localised_title_case_insensitively(self) -> None:
        store = InMemoryStore()
        await save_good(store)
        await store.save_presentation(build_presentation(title='Mountain Lake'))

        page = await build_catalogue(store).page(
            Locale.EN, CatalogueSort.NEWEST, 'mountain', None, None, 24, 0
        )

        assert tuple(card.candidate_id for card in page.items) == ('openverse:1',)
        assert page.total == 1

    async def test_a_term_matches_the_source_title(self) -> None:
        store = InMemoryStore()
        await save_good(store, title='Sunset over Minsk')
        await store.save_presentation(build_presentation(title='Evening'))

        page = await build_catalogue(store).page(
            Locale.EN, CatalogueSort.NEWEST, 'minsk', None, None, 24, 0
        )

        assert page.total == 1

    async def test_a_term_matches_the_creator(self) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry('openverse:1'))
        await store.upsert_many(
            (
                build_candidate(candidate_id='openverse:1').model_copy(
                    update={'creator': 'Ada Lovelace'}
                ),
            )
        )

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, 'lovelace', None, None, 24, 0
        )

        assert page.total == 1

    async def test_a_term_that_matches_nothing_returns_an_empty_page(self) -> None:
        store = InMemoryStore()
        await save_good(store)

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, 'no-such-good', None, None, 24, 0
        )

        assert page.items == ()
        assert page.total == 0

    async def test_a_term_narrows_the_total_to_what_matched(self) -> None:
        store = InMemoryStore()
        for index in range(4):
            await save_good(store, f'openverse:{index}')
        await store.save_presentation(build_presentation('openverse:2', title='Match me'))

        page = await build_catalogue(store).page(
            Locale.EN, CatalogueSort.NEWEST, 'match', None, None, 24, 0
        )

        assert page.total == 1


class TestFilters:
    async def test_a_category_slug_narrows_the_page(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())
        await save_good(store, 'openverse:1', category_id='cat-photography')
        await save_good(store, 'openverse:2')

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, 'photography', None, 24, 0
        )

        assert tuple(card.candidate_id for card in page.items) == ('openverse:1',)
        assert page.total == 1

    async def test_an_unknown_category_slug_matches_nothing(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())
        await save_good(store, category_id='cat-photography')

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, 'missing', None, 24, 0
        )

        assert page.items == ()
        assert page.total == 0

    async def test_a_licence_filter_excludes_the_others(self) -> None:
        store = InMemoryStore()
        await save_good(store, 'openverse:1', license_id='CC0-1.0')
        await save_good(store, 'openverse:2', license_id='CC-BY-4.0')

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, 'CC0-1.0', 24, 0
        )

        assert tuple(card.candidate_id for card in page.items) == ('openverse:1',)

    async def test_a_licence_and_a_category_are_applied_together(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())
        await save_good(store, 'openverse:1', category_id='cat-photography', license_id='CC0-1.0')
        await save_good(store, 'openverse:2', category_id='cat-other', license_id='CC0-1.0')

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, 'photography', 'CC0-1.0', 24, 0
        )

        assert tuple(card.candidate_id for card in page.items) == ('openverse:1',)


class TestCatalogueCard:
    async def test_a_card_carries_what_a_buyer_needs(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())
        await save_good(
            store,
            'openverse:1',
            title='Source title',
            category_id='cat-photography',
            published_at=NOW,
        )
        await store.save_presentation(
            build_presentation(title='Display title', summary='A summary')
        )

        page = await build_catalogue(store).page(
            Locale.EN, CatalogueSort.NEWEST, None, None, None, 24, 0
        )

        assert page.items[0] == CatalogueCard(
            candidate_id='openverse:1',
            title='Display title',
            original_title='Source title',
            summary='A summary',
            creator='Example Author',
            license_id='CC-BY-4.0',
            obligations=('Credit the creator',),
            category_id='cat-photography',
            category_slug='photography',
            unit_amount='9.99',
            currency='BYN',
            preview_url='/catalogue/goods/openverse:1/preview',
            preview_is_cover=False,
            content_type='image',
            size_bytes=1024,
            published_at=NOW,
        )

    async def test_a_card_never_carries_the_origin_or_a_storage_location(self) -> None:
        store = InMemoryStore()
        await save_good(store)

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0
        )
        dumped = page.items[0].model_dump()

        for key in FORBIDDEN_KEYS:
            assert key not in dumped
        assert ORIGIN_URL not in str(dumped)

    async def test_a_cover_is_announced_on_the_card(self) -> None:
        store = InMemoryStore()
        await save_good(store)
        await store.save_cover(build_cover())

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0
        )

        assert page.items[0].preview_is_cover is True

    async def test_a_size_the_source_never_reported_stays_unknown(self) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry('openverse:1'))
        await store.upsert_many(
            (
                build_candidate(candidate_id='openverse:1').model_copy(
                    update={'size_bytes': None}
                ),
            )
        )

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0
        )

        assert page.items[0].size_bytes is None


class TestCatalogueCardLookup:
    async def test_a_published_good_has_a_card(self) -> None:
        store = InMemoryStore()
        await save_good(store)

        card = await build_catalogue(store).card('openverse:1', Locale.RU)

        assert card is not None
        assert card.candidate_id == 'openverse:1'

    @pytest.mark.parametrize(
        'entry',
        [
            build_entry('openverse:1', state=CatalogueEntryState.WITHDRAWN),
            build_entry('openverse:1', listing=StorefrontListing.FREE_ONLY),
        ],
    )
    async def test_a_good_the_gate_did_not_release_has_no_card(
        self, entry: CatalogueEntry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many((build_candidate(candidate_id='openverse:1'),))
        await store.save_entry(entry)

        assert await build_catalogue(store).card('openverse:1', Locale.RU) is None

    async def test_an_unknown_good_has_no_card(self) -> None:
        catalogue = build_catalogue(InMemoryStore())

        assert await catalogue.card('openverse:missing', Locale.RU) is None

    async def test_the_requested_locale_resolves_on_a_single_card(self) -> None:
        store = InMemoryStore()
        await save_good(store)
        await store.save_presentation(build_presentation(title='English title'))

        card = await build_catalogue(store).card('openverse:1', Locale.EN)

        assert card is not None
        assert card.title == 'English title'


class TestCategories:
    async def test_a_summary_counts_the_saleable_goods_of_a_category(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())
        await store.save_category(build_category('cat-audio', 'Audio', 'audio'))
        await save_good(store, 'openverse:1', category_id='cat-photography')
        await save_good(store, 'openverse:2', category_id='cat-photography')
        await save_good(
            store,
            'openverse:3',
            category_id='cat-photography',
            state=CatalogueEntryState.WITHDRAWN,
        )

        summaries = await build_catalogue(store).category_summaries(Locale.RU)

        assert tuple((item.slug, item.count) for item in summaries) == (
            ('audio', 0),
            ('photography', 2),
        )

    async def test_a_category_page_returns_its_summary_and_goods(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())
        await save_good(store, category_id='cat-photography')

        page = await build_catalogue(store).category_page('photography', Locale.RU, 24, 0)

        assert page is not None
        assert page.summary.slug == 'photography'
        assert page.total == 1
        assert tuple(card.candidate_id for card in page.items) == ('openverse:1',)

    async def test_an_unknown_category_has_no_page(self) -> None:
        catalogue = build_catalogue(InMemoryStore())

        assert await catalogue.category_page('missing', Locale.RU, 24, 0) is None

    async def test_an_empty_category_is_a_page_with_no_goods(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())

        page = await build_catalogue(store).category_page('photography', Locale.RU, 24, 0)

        assert page is not None
        assert page.items == ()
        assert page.total == 0

    async def test_each_locale_reads_its_own_name_with_the_same_count(self) -> None:
        store = InMemoryStore()
        await store.save_category(
            build_category(
                names=(
                    CategoryName(locale=Locale.RU, name='Фотография'),
                    CategoryName(locale=Locale.BE, name='Фатаграфія'),
                    CategoryName(locale=Locale.EN, name='Photography'),
                )
            )
        )
        await save_good(store, 'openverse:1', category_id='cat-photography')
        catalogue = build_catalogue(store)

        summaries = {
            locale: await catalogue.category_summaries(locale) for locale in Locale
        }

        assert summaries[Locale.RU][0].name == 'Фотография'
        assert summaries[Locale.BE][0].name == 'Фатаграфія'
        assert summaries[Locale.EN][0].name == 'Photography'
        assert {rows[0].count for rows in summaries.values()} == {1}

    async def test_a_category_with_no_names_is_omitted_from_the_summaries(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category(names=()))

        summaries = await build_catalogue(store).category_summaries(Locale.EN)

        assert summaries == ()

    async def test_a_missing_language_falls_back_to_the_shops_language(self) -> None:
        store = InMemoryStore()
        await store.save_category(
            build_category(
                names=(CategoryName(locale=Locale.RU, name='Фотография'),)
            )
        )

        summaries = await build_catalogue(store).category_summaries(Locale.EN)

        assert tuple(summary.name for summary in summaries) == ('Фотография',)

    async def test_a_nameless_category_has_no_page(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category(names=()))
        await save_good(store, category_id='cat-photography')

        assert (
            await build_catalogue(store).category_page('photography', Locale.RU, 24, 0)
            is None
        )


class TestSaleabilityAgreement:
    async def test_the_service_and_the_store_agree_on_what_is_saleable(self) -> None:
        store = InMemoryStore()
        await save_good(store, 'openverse:1')
        await save_good(store, 'openverse:2', listing=StorefrontListing.FREE_ONLY)

        page = await build_catalogue(store).page(
            Locale.RU, CatalogueSort.NEWEST, None, None, None, 24, 0
        )

        assert len(page.items) == 1
        for card in page.items:
            entry = await store.by_candidate(card.candidate_id)
            assert entry is not None
            assert SaleableEntry.matches(entry)
