from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from pydantic import BaseModel

from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, SaleableEntry
from packages.services.src.domain.catalogue_card import (
    CatalogueCard,
    CataloguePage,
    CategoryPage,
    CategorySummary,
)
from packages.services.src.domain.catalogue_query import CatalogueFilter, CatalogueSort
from packages.services.src.domain.category import Category
from packages.services.src.domain.presentation import (
    DEFAULT_LOCALE,
    Locale,
    ResolvedPresentation,
)
from packages.services.src.persistence.contract import (
    CandidateRepository,
    CatalogueCoverRepository,
    CatalogueEntryRepository,
    CategoryRepository,
    StorefrontCatalog,
)


class _CatalogueRow(BaseModel):
    """One catalogue entry joined with everything a card needs to present it."""

    model_config = {'frozen': True}

    entry: CatalogueEntry
    candidate: Candidate
    resolved: ResolvedPresentation
    unit_amount: Decimal
    category_slug: str | None
    preview_is_cover: bool


class StorefrontCatalogue:
    """The read path a buyer's catalogue is built from.

    The ordering the buyer asked for is applied here rather than in the store,
    and that is a deliberate limit: ``title_asc`` orders by the title resolved
    for the requested locale, which is not a column, so no SQL can produce it.
    The catalogue is on the order of a hundred goods and a query per locale in
    the database is not worth it yet; when per-locale title ordering is needed at
    a size where this hurts, the presentation becomes a column to sort on.

    Nothing here decides what may be sold. A query reads the catalogue, and an
    entry that is not ``PUBLISHED`` and ``PAID_OK`` is absent from every one of
    them, so this service cannot become a second door to the storefront.
    """

    PREVIEW_PATH_TEMPLATE = '/catalogue/goods/{candidate_id}/preview'

    def __init__(
        self,
        catalog: StorefrontCatalog,
        entries: CatalogueEntryRepository,
        categories: CategoryRepository,
        candidates: CandidateRepository,
        covers: CatalogueCoverRepository,
        presentations: PresentationService,
        unit_amount: Decimal,
        currency: str,
    ) -> None:
        self._catalog = catalog
        self._entries = entries
        self._categories = categories
        self._candidates = candidates
        self._covers = covers
        self._presentations = presentations
        self._unit_amount = unit_amount
        self._currency = currency

    async def page(
        self,
        locale: Locale,
        sort: CatalogueSort,
        text: str | None,
        category_slug: str | None,
        license_id: str | None,
        limit: int,
        offset: int,
    ) -> CataloguePage:
        category_id = await self._category_id_for(category_slug)
        if category_slug is not None and category_id is None:
            return CataloguePage(items=(), total=0, limit=limit, offset=offset)
        matches = await self._catalog.search(
            CatalogueFilter(category_id=category_id, license_id=license_id)
        )
        rows = await self._rows_for(matches.entries, locale)
        located = self._matching_text(rows, text)
        # With a text term the store could not count, because the term matches
        # the localised title; without one its own count is the answer.
        total = len(located) if text is not None else matches.total
        ordered = self._ordered(located, sort)
        return CataloguePage(
            items=tuple(self._card(row) for row in ordered[offset : offset + limit]),
            total=total,
            limit=limit,
            offset=offset,
        )

    async def card(self, candidate_id: str, locale: Locale) -> CatalogueCard | None:
        """The card for one good, or ``None`` when no buyer may see it.

        ``None`` covers unknown, withdrawn and not-paid-ok alike, because the
        buyer's page shows the same 404 for all three and telling them apart
        would describe goods the gate refused.
        """
        entry = await self._entries.by_candidate(candidate_id)
        if entry is None or not SaleableEntry.matches(entry):
            return None
        candidate = await self._candidate_for(entry)
        resolved = await self._presentations.resolve(candidate, locale)
        cover = await self._covers.cover_for(candidate_id)
        return self._card(
            _CatalogueRow(
                entry=entry,
                candidate=candidate,
                resolved=resolved,
                unit_amount=self._unit_amount,
                category_slug=await self._category_slug_for(entry.category_id),
                preview_is_cover=cover is not None,
            )
        )

    async def category_summaries(self, locale: Locale) -> tuple[CategorySummary, ...]:
        """Every category the operator has, with how many saleable goods it holds.

        The count is the number of goods a buyer can actually buy in it, not the
        number assigned, so a category that holds only withdrawn goods reads as
        empty rather than as full.
        """
        categories = await self._categories.all()
        counts = {
            row.category_id: row.count for row in await self._catalog.counts_by_category()
        }
        summaries: list[CategorySummary] = []
        for category in categories:
            name = self._resolved_category_name(category, locale)
            if name is None:
                continue
            summaries.append(
                CategorySummary(
                    category_id=category.category_id,
                    name=name,
                    slug=category.slug,
                    count=counts[category.category_id]
                    if category.category_id in counts
                    else 0,
                )
            )
        return tuple(summaries)

    async def category_page(
        self, slug: str, locale: Locale, limit: int, offset: int
    ) -> CategoryPage | None:
        category = await self._categories.by_slug(slug)
        if category is None:
            return None
        name = self._resolved_category_name(category, locale)
        if name is None:
            # A category with no name in any language has no label to head its
            # page with, and a slug is not a label. It reads as not found rather
            # than as a page under a raw identifier.
            return None
        page = await self.page(
            locale, CatalogueSort.NEWEST, None, slug, None, limit, offset
        )
        return CategoryPage(
            summary=CategorySummary(
                category_id=category.category_id,
                name=name,
                slug=category.slug,
                count=page.total,
            ),
            items=page.items,
            total=page.total,
        )

    async def _rows_for(
        self, entries: tuple[CatalogueEntry, ...], locale: Locale
    ) -> tuple[_CatalogueRow, ...]:
        candidates = await self._candidates_for(entries)
        resolved = await self._presentations.resolve_many(candidates, locale)
        slugs = {category.category_id: category.slug for category in await self._categories.all()}
        covers = {cover.candidate_id for cover in await self._covers.all_covers()}
        rows: list[_CatalogueRow] = []
        for entry, candidate, resolution in zip(entries, candidates, resolved, strict=True):
            category_slug: str | None = None
            if entry.category_id is not None:
                category_slug = slugs.get(entry.category_id)
            rows.append(
                _CatalogueRow(
                    entry=entry,
                    candidate=candidate,
                    resolved=resolution,
                    unit_amount=self._unit_amount,
                    category_slug=category_slug,
                    preview_is_cover=entry.candidate_id in covers,
                )
            )
        return tuple(rows)

    async def _candidates_for(
        self, entries: tuple[CatalogueEntry, ...]
    ) -> tuple[Candidate, ...]:
        candidates: list[Candidate] = []
        for entry in entries:
            candidates.append(await self._candidate_for(entry))
        return tuple(candidates)

    async def _candidate_for(self, entry: CatalogueEntry) -> Candidate:
        candidate = await self._candidates.by_candidate_id(entry.candidate_id)
        if candidate is None:
            raise RuntimeError(
                f'catalogue entry {entry.candidate_id} has no candidate row'
            )
        return candidate

    async def _category_id_for(self, slug: str | None) -> str | None:
        if slug is None:
            return None
        category = await self._categories.by_slug(slug)
        if category is None:
            return None
        return category.category_id

    async def _category_slug_for(self, category_id: str | None) -> str | None:
        if category_id is None:
            return None
        category = await self._categories.by_id(category_id)
        if category is None:
            return None
        return category.slug

    @staticmethod
    def _resolved_category_name(category: Category, locale: Locale) -> str | None:
        """The buyer-facing name for a language, on the shop's fallback rule.

        The requested language first, then ``DEFAULT_LOCALE``, then ``None``,
        the same rule ``PresentationService`` applies to a good's title. The
        scalar ``category.name`` is never returned here: it is the external
        catalogue and ordering label, and a buyer reads a resolved name.

        ``None`` is a real absence, and the caller decides what to do with it: a
        category nothing can name is not a category a buyer may be shown under a
        raw identifier.
        """
        for candidate_locale in (locale, DEFAULT_LOCALE):
            for name in category.names:
                if name.locale is candidate_locale:
                    return name.name
        return None

    @staticmethod
    def _matching_text(
        rows: tuple[_CatalogueRow, ...], text: str | None
    ) -> tuple[_CatalogueRow, ...]:
        if text is None:
            return rows
        needle = text.casefold()
        return tuple(row for row in rows if StorefrontCatalogue._row_matches(row, needle))

    @staticmethod
    def _row_matches(row: _CatalogueRow, needle: str) -> bool:
        if needle in row.resolved.title.casefold():
            return True
        if needle in row.resolved.original_title.casefold():
            return True
        if row.candidate.creator is None:
            return False
        return needle in row.candidate.creator.casefold()

    @classmethod
    def _ordered(
        cls, rows: tuple[_CatalogueRow, ...], sort: CatalogueSort
    ) -> tuple[_CatalogueRow, ...]:
        key, reverse = cls._order_for(sort)
        by_candidate = sorted(rows, key=lambda row: row.candidate.id)
        return tuple(sorted(by_candidate, key=key, reverse=reverse))

    @staticmethod
    def _order_for(
        sort: CatalogueSort,
    ) -> tuple[Callable[[_CatalogueRow], object], bool]:
        match sort:
            case CatalogueSort.NEWEST:
                return (lambda row: row.entry.published_at, True)
            case CatalogueSort.PRICE_ASC:
                return (lambda row: row.unit_amount, False)
            case CatalogueSort.PRICE_DESC:
                return (lambda row: row.unit_amount, True)
            case CatalogueSort.TITLE_ASC:
                return (lambda row: row.resolved.title.casefold(), False)
            case CatalogueSort.TITLE_DESC:
                return (lambda row: row.resolved.title.casefold(), True)

    def _card(self, row: _CatalogueRow) -> CatalogueCard:
        return CatalogueCard(
            candidate_id=row.entry.candidate_id,
            title=row.resolved.title,
            original_title=row.resolved.original_title,
            summary=row.resolved.summary,
            creator=row.candidate.creator,
            license_id=row.entry.license_id,
            obligations=row.entry.obligations,
            category_id=row.entry.category_id,
            category_slug=row.category_slug,
            unit_amount=format(row.unit_amount, 'f'),
            currency=self._currency,
            preview_url=self.PREVIEW_PATH_TEMPLATE.format(
                candidate_id=row.entry.candidate_id
            ),
            preview_is_cover=row.preview_is_cover,
            content_type=row.candidate.content_type,
            size_bytes=row.candidate.size_bytes,
            published_at=row.entry.published_at,
        )
