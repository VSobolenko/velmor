from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic_ai.models.test import TestModel

from packages.services.src.commerce.category_service import CategoryService
from packages.services.src.commerce.curation import CatalogueCurator, CurationService
from packages.services.src.commerce.errors import CurationRefusedError
from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.commerce.slugs import CategorySlug, ProductSlug
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.catalogue_query import CatalogueFilter
from packages.services.src.domain.category import Category
from packages.services.src.domain.curation import CurationProposal, LocaleCopy
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.presentation import (
    CataloguePresentation,
    Locale,
    PresentationSource,
)
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.saleor.client import SaleorCategory, SaleorProduct
from packages.services.tests.conftest import build_candidate

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 20, 18, 0, tzinfo=UTC)
FIRST = 'openverse:1'
SECOND = 'openverse:2'
SLUG = 'photography'
CATEGORY_NAME = 'Фотография'
TITLE = 'Ночная съёмка'


class FakeSaleor:
    """Records the Saleor calls a category assignment makes; returns stable ids."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self._sequence = 0

    async def create_category(self, name: str, slug: str) -> SaleorCategory:
        self.calls.append(('create_category', name, slug))
        self._sequence += 1
        return SaleorCategory(category_id=f'saleor-cat-{self._sequence}')

    async def update_category(self, category_id: str, name: str, slug: str) -> SaleorCategory:
        self.calls.append(('update_category', category_id, name, slug))
        return SaleorCategory(category_id=category_id)

    async def delete_category(self, category_id: str) -> None:
        self.calls.append(('delete_category', category_id))

    async def update_product(
        self, product_id: str, name: str, slug: str, category_id: str | None
    ) -> SaleorProduct:
        self.calls.append(('update_product', product_id, name, slug, category_id))
        return SaleorProduct(product_id=product_id)


class FixedProposer:
    """Proposes the same copy and category for whoever it is asked about."""

    def __init__(
        self,
        slug: str = SLUG,
        category_name: str = CATEGORY_NAME,
        title: str = TITLE,
        summary: str = 'Снимок города после заката.',
    ) -> None:
        self._slug = slug
        self._category_name = category_name
        self._title = title
        self._summary = summary
        self.asked: list[str] = []

    async def propose(self, candidate: Candidate) -> CurationProposal:
        self.asked.append(candidate.id)
        return CurationProposal(
            candidate_id=candidate.id,
            copy_by_locale=(
                LocaleCopy(locale=Locale.RU, title=self._title, summary=self._summary),
                LocaleCopy(
                    locale=Locale.BE,
                    title=f'{self._title} (be)',
                    summary=f'{self._summary} (be)',
                ),
                LocaleCopy(
                    locale=Locale.EN,
                    title=f'{self._title} (en)',
                    summary=f'{self._summary} (en)',
                ),
            ),
            category_slug=self._slug,
            category_name=self._category_name,
        )


class Asker:
    """A proposer that returns one prepared proposal and records being asked."""

    def __init__(self, proposal: CurationProposal) -> None:
        self._proposal = proposal
        self.asked: list[str] = []

    async def propose(self, candidate: Candidate) -> CurationProposal:
        self.asked.append(candidate.id)
        return self._proposal


def published_entry(candidate_id: str = FIRST) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id=f'product-{candidate_id}',
        saleor_variant_id=f'variant-{candidate_id}',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=('credit the creator',),
        listing=StorefrontListing.PAID_OK,
        state=CatalogueEntryState.PUBLISHED,
        withdrawal_reason=None,
        published_at=NOW,
        content_digest='00' * 32,
        origin_url='https://openverse.test/items/1.bin',
    )


def withdrawn_entry(candidate_id: str) -> CatalogueEntry:
    return published_entry(candidate_id).model_copy(
        update={
            'state': CatalogueEntryState.WITHDRAWN,
            'withdrawal_reason': 'withdrawn for test',
        }
    )


def build_proposal(candidate_id: str = FIRST) -> CurationProposal:
    return CurationProposal(
        candidate_id=candidate_id,
        copy_by_locale=(
            LocaleCopy(locale=Locale.RU, title='Ночь', summary='Сводка'),
            LocaleCopy(locale=Locale.BE, title='Ноч', summary='Зводка'),
            LocaleCopy(locale=Locale.EN, title='Night', summary='Summary'),
        ),
        category_slug=SLUG,
        category_name=CATEGORY_NAME,
    )


def build_service(
    store: InMemoryStore,
    proposer: object,
    saleor: FakeSaleor | None = None,
) -> CurationService:
    return CurationService(
        catalog=store,
        candidates=store,
        presentations=PresentationService(store),
        categories=store,
        category_service=CategoryService(
            categories=store,
            entries=store,
            saleor=saleor if saleor is not None else FakeSaleor(),
        ),
        proposer=proposer,
        clock=lambda: LATER,
    )


async def stock(store: InMemoryStore, *candidate_ids: str) -> None:
    for candidate_id in candidate_ids:
        await store.upsert_many((build_candidate(candidate_id=candidate_id),))
        await store.save_entry(published_entry(candidate_id))


async def store_category(store: InMemoryStore, name: str = CATEGORY_NAME, slug: str = SLUG) -> None:
    await store.save_category(
        Category(
            category_id=f'cat-{slug}',
            name=name,
            slug=slug,
            saleor_category_id=f'saleor-{slug}',
            created_at=NOW,
        )
    )


async def store_russian(store: InMemoryStore, candidate_id: str) -> None:
    await store.save_presentation(
        CataloguePresentation(
            candidate_id=candidate_id,
            locale=Locale.RU,
            title='Своё название',
            summary='Своя сводка',
            source=PresentationSource.OPERATOR,
            updated_at=NOW,
        )
    )


class TestFillingMissingCopy:
    async def test_a_run_stores_copy_for_every_served_language(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        proposer = FixedProposer()

        run = await build_service(store, proposer).fill_missing(50)

        assert tuple(outcome.wrote_presentation for outcome in run.outcomes) == (True,)
        stored = await store.presentations_for(FIRST)
        assert {row.locale for row in stored} == set(Locale)
        russian = next(row for row in stored if row.locale is Locale.RU)
        assert russian.title == TITLE
        assert russian.source is PresentationSource.MODEL
        assert russian.updated_at == LATER

    async def test_a_good_already_curated_is_not_asked_about_again(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        proposer = FixedProposer()
        service = build_service(store, proposer)

        await service.fill_missing(50)
        second = await service.fill_missing(50)

        assert proposer.asked == [FIRST]
        assert tuple(outcome.wrote_presentation for outcome in second.outcomes) == (False,)
        assert second.outcomes[0].category_slug == SLUG

    async def test_only_the_languages_without_copy_are_written(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        await store_russian(store, FIRST)

        await build_service(store, FixedProposer()).fill_missing(50)

        stored = await store.presentations_for(FIRST)
        russian = next(row for row in stored if row.locale is Locale.RU)
        assert russian.title == 'Своё название'
        assert russian.source is PresentationSource.OPERATOR
        assert {row.locale for row in stored} == set(Locale)

    async def test_a_run_is_bounded_by_the_limit(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST, SECOND, 'openverse:3')
        proposer = FixedProposer()

        run = await build_service(store, proposer).fill_missing(2)

        assert len(run.outcomes) == 2
        assert proposer.asked == [FIRST, SECOND]

    async def test_a_run_reports_a_good_it_walked_past(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST, SECOND)
        await store_russian(store, FIRST)
        await store.save_presentation(
            CataloguePresentation(
                candidate_id=FIRST,
                locale=Locale.BE,
                title='Своё',
                summary='Своя',
                source=PresentationSource.OPERATOR,
                updated_at=NOW,
            )
        )
        await store.save_presentation(
            CataloguePresentation(
                candidate_id=FIRST,
                locale=Locale.EN,
                title='Своё',
                summary='Своя',
                source=PresentationSource.OPERATOR,
                updated_at=NOW,
            )
        )

        run = await build_service(store, FixedProposer()).fill_missing(50)

        by_candidate = {outcome.candidate_id: outcome for outcome in run.outcomes}
        assert by_candidate[FIRST].wrote_presentation is False
        assert by_candidate[SECOND].wrote_presentation is True


class TestCategoryAssignment:
    async def test_a_run_creates_the_category_and_assigns_the_good(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        saleor = FakeSaleor()

        run = await build_service(store, FixedProposer(), saleor).fill_missing(50)

        assert run.outcomes[0].category_slug == SLUG
        category = await store.by_slug(SLUG)
        assert category is not None
        assert category.name == CATEGORY_NAME
        assert category.category_id == f'cat-{SLUG}'
        entry = await store.by_candidate(FIRST)
        assert entry is not None
        assert entry.category_id == category.category_id
        assert saleor.calls == [
            ('create_category', CATEGORY_NAME, SLUG),
            (
                'update_product',
                f'product-{FIRST}',
                TITLE,
                ProductSlug.for_candidate(FIRST),
                category.saleor_category_id,
            ),
        ]

    async def test_an_existing_category_is_reused(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        await store_category(store)
        saleor = FakeSaleor()

        await build_service(store, FixedProposer(), saleor).fill_missing(50)

        assert [call for call in saleor.calls if call[0] == 'create_category'] == []
        entry = await store.by_candidate(FIRST)
        assert entry is not None
        assert entry.category_id == f'cat-{SLUG}'

    async def test_a_good_already_categorised_is_not_reassigned(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        await store_category(store)
        await store.save_entry(published_entry(FIRST).model_copy(update={'category_id': f'cat-{SLUG}'}))
        saleor = FakeSaleor()

        await build_service(store, FixedProposer(), saleor).fill_missing(50)

        assert [call for call in saleor.calls if call[0] == 'update_product'] == []
        entry = await store.by_candidate(FIRST)
        assert entry is not None
        assert entry.category_id == f'cat-{SLUG}'

    async def test_a_good_of_another_category_is_reassigned(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        await store_category(store, name='Книги', slug='books')
        await store.save_entry(published_entry(FIRST).model_copy(update={'category_id': 'cat-books'}))

        await build_service(store, FixedProposer()).fill_missing(50)

        entry = await store.by_candidate(FIRST)
        assert entry is not None
        assert entry.category_id == f'cat-{SLUG}'


class TestTheCatalogueIsNotChanged:
    async def test_the_run_writes_no_verdict_and_no_saleable_state(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST, SECOND)
        filter_all = CatalogueFilter(category_id=None, license_id=None)
        published_before = await store.published(50)
        saleable_before = tuple(
            (entry.candidate_id, entry.state, entry.listing, entry.license_id)
            for entry in (await store.search(filter_all)).entries
        )
        decisions_before = store.decisions()

        await build_service(store, FixedProposer()).fill_missing(50)

        assert await store.published(50) == published_before
        assert (
            tuple(
                (entry.candidate_id, entry.state, entry.listing, entry.license_id)
                for entry in (await store.search(filter_all)).entries
            )
            == saleable_before
        )
        assert store.decisions() == decisions_before

    async def test_a_good_the_gate_refused_is_not_walked(self) -> None:
        store = InMemoryStore()
        await store.upsert_many((build_candidate(candidate_id=FIRST),))
        await store.save_entry(withdrawn_entry(FIRST))
        proposer = FixedProposer()

        run = await build_service(store, proposer).fill_missing(50)

        assert run.outcomes == ()
        assert proposer.asked == []
        assert await store.presentations_for(FIRST) == ()

    async def test_a_good_already_in_its_category_writes_nothing_to_saleor(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        await store_category(store)
        await store.save_entry(
            published_entry(FIRST).model_copy(update={'category_id': f'cat-{SLUG}'})
        )
        saleor = FakeSaleor()

        await build_service(store, FixedProposer(), saleor).fill_missing(50)

        assert saleor.calls == []


class TestRefusedProposals:
    async def test_a_proposal_for_another_good_is_refused(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        proposer = Asker(build_proposal(SECOND))

        with pytest.raises(CurationRefusedError):
            await build_service(store, proposer).fill_missing(50)

        assert await store.presentations_for(FIRST) == ()

    async def test_a_proposal_missing_a_language_is_refused(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        proposal = build_proposal().model_copy(
            update={
                'copy_by_locale': (
                    LocaleCopy(locale=Locale.RU, title='Ночь', summary='Сводка'),
                )
            }
        )

        with pytest.raises(CurationRefusedError):
            await build_service(store, Asker(proposal)).fill_missing(50)

        assert await store.presentations_for(FIRST) == ()

    async def test_a_proposal_with_an_empty_title_is_refused(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)
        proposal = build_proposal().model_copy(
            update={
                'copy_by_locale': (
                    LocaleCopy(locale=Locale.RU, title='   ', summary='Сводка'),
                    LocaleCopy(locale=Locale.BE, title='Ноч', summary='Зводка'),
                    LocaleCopy(locale=Locale.EN, title='Night', summary='Summary'),
                )
            }
        )

        with pytest.raises(CurationRefusedError):
            await build_service(store, Asker(proposal)).fill_missing(50)

        assert await store.presentations_for(FIRST) == ()

    async def test_a_proposal_that_names_neither_category_is_refused(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)

        for proposal in (
            build_proposal().model_copy(update={'category_slug': 'Not A Slug'}),
            build_proposal().model_copy(update={'category_name': '  '}),
        ):
            with pytest.raises(CurationRefusedError):
                await build_service(store, Asker(proposal)).fill_missing(50)

        assert await store.by_slug('Not A Slug') is None
        assert await store.by_slug(SLUG) is None

    async def test_a_good_with_no_candidate_row_is_not_curated(self) -> None:
        store = InMemoryStore()
        await store.save_entry(published_entry(FIRST))
        proposer = FixedProposer()

        with pytest.raises(CurationRefusedError):
            await build_service(store, proposer).fill_missing(50)

        assert proposer.asked == []


class TestCatalogueCurator:
    async def test_the_proposal_answers_for_every_served_language(self) -> None:
        curator = CatalogueCurator(TestModel())

        proposal = await curator.propose(build_candidate(candidate_id=FIRST, title='DSC_0421.png'))

        assert proposal.candidate_id == FIRST
        assert tuple(copy.locale for copy in proposal.copy_by_locale) == tuple(Locale)
        assert all(copy.title.strip() != '' for copy in proposal.copy_by_locale)
        assert all(copy.summary.strip() != '' for copy in proposal.copy_by_locale)
        assert CategorySlug.is_valid(proposal.category_slug)
        assert proposal.category_name.strip() != ''

    async def test_the_prompt_carries_the_record_and_not_the_origin_url(self) -> None:
        curator = CatalogueCurator(TestModel())
        candidate = build_candidate(candidate_id=FIRST, title='DSC_0421.png')

        prompt = curator._prompt(candidate)

        assert 'DSC_0421.png' in prompt
        assert 'Example Author' in prompt
        assert candidate.landing_url not in prompt
        assert candidate.download_url not in prompt

    async def test_the_prompt_names_an_unknown_creator_as_unknown(self) -> None:
        curator = CatalogueCurator(TestModel())
        candidate = build_candidate(candidate_id=FIRST).model_copy(update={'creator': None})

        assert 'unknown' in curator._prompt(candidate)


class TestTheResolutionSeesTheStoredCopy:
    async def test_the_curated_title_is_what_a_locale_resolves_to(self) -> None:
        store = InMemoryStore()
        await stock(store, FIRST)

        await build_service(store, FixedProposer()).fill_missing(50)

        resolved = await PresentationService(store).resolve(
            build_candidate(candidate_id=FIRST), Locale.EN
        )
        assert resolved.title == f'{TITLE} (en)'
        assert resolved.is_fallback_title is False
