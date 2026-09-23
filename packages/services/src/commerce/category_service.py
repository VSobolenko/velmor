from __future__ import annotations

from datetime import datetime
from typing import Protocol

from packages.services.src.commerce.errors import (
    CatalogueEntryNotFoundError,
    CatalogueEntryNotPublishedError,
    CategoryNotEmptyError,
    CategoryNotFoundError,
    CategorySlugTakenError,
)
from packages.services.src.commerce.slugs import ProductSlug
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.category import Category, CategoryName
from packages.services.src.persistence.contract import (
    CatalogueEntryRepository,
    CategoryRepository,
)
from packages.services.src.saleor.client import SaleorCategory, SaleorProduct


class SaleorCategoryPort(Protocol):
    """The Saleor operations category management uses."""

    async def create_category(self, name: str, slug: str) -> SaleorCategory: ...

    async def update_category(
        self, category_id: str, name: str, slug: str
    ) -> SaleorCategory: ...

    async def delete_category(self, category_id: str) -> None: ...

    async def update_product(
        self, product_id: str, name: str, slug: str, category_id: str | None
    ) -> SaleorProduct: ...


class CategoryService:
    """Create, rename, remove and assign storefront categories.

    Category mappings are stored data on catalogue entries. A model's suggestion
    of a name is applied here as an argument and never resolved at render time
    (design D4). Saleor errors propagate; this service does not catch them.
    """

    def __init__(
        self,
        categories: CategoryRepository,
        entries: CatalogueEntryRepository,
        saleor: SaleorCategoryPort,
    ) -> None:
        self._categories = categories
        self._entries = entries
        self._saleor = saleor

    async def create(
        self,
        name: str,
        slug: str,
        names: tuple[CategoryName, ...],
        now: datetime,
    ) -> Category:
        """Create a category, giving Saleor exactly one name and storing them all.

        ``name`` is the single scalar the external catalogue node receives;
        ``names`` are the buyer-facing names per language. The two are separate
        because a Saleor node has one name and the shop serves several.
        """
        if await self._categories.by_slug(slug) is not None:
            raise CategorySlugTakenError(f'category slug {slug!r} is already taken')
        saleor_category = await self._saleor.create_category(name=name, slug=slug)
        category = Category(
            category_id=self._id_for(slug),
            name=name,
            slug=slug,
            saleor_category_id=saleor_category.category_id,
            created_at=now,
            names=names,
        )
        await self._categories.save_category(category)
        return category

    async def rename(
        self,
        category_id: str,
        new_name: str,
        new_slug: str,
        new_names: tuple[CategoryName, ...],
    ) -> Category:
        """Rename a category, sending Saleor one name and replacing all names.

        ``new_name`` is the single scalar the external catalogue node receives;
        ``new_names`` are the buyer-facing names per language.
        """
        existing = await self._require_category(category_id)
        occupant = await self._categories.by_slug(new_slug)
        if occupant is not None and occupant.category_id != category_id:
            raise CategorySlugTakenError(f'category slug {new_slug!r} is already taken')
        await self._saleor.update_category(
            category_id=existing.saleor_category_id,
            name=new_name,
            slug=new_slug,
        )
        renamed = Category(
            category_id=existing.category_id,
            name=new_name,
            slug=new_slug,
            saleor_category_id=existing.saleor_category_id,
            created_at=existing.created_at,
            names=new_names,
        )
        await self._categories.save_category(renamed)
        return renamed

    async def remove(self, category_id: str) -> None:
        existing = await self._require_category(category_id)
        blockers = await self._entries.by_category(category_id)
        if blockers:
            raise CategoryNotEmptyError(
                f'category {category_id!r} still holds entries',
                blocking_candidate_ids=tuple(entry.candidate_id for entry in blockers),
            )
        await self._saleor.delete_category(existing.saleor_category_id)
        await self._categories.delete_category(category_id)

    async def assign(
        self, candidate_id: str, category_id: str, product_name: str
    ) -> CatalogueEntry:
        entry = await self._require_published_entry(candidate_id)
        category = await self._require_category(category_id)
        await self._saleor.update_product(
            product_id=entry.saleor_product_id,
            name=product_name,
            slug=ProductSlug.for_candidate(candidate_id),
            category_id=category.saleor_category_id,
        )
        updated = entry.model_copy(update={'category_id': category.category_id})
        await self._entries.save_entry(updated)
        return updated

    async def unassign(self, candidate_id: str, product_name: str) -> CatalogueEntry:
        entry = await self._require_published_entry(candidate_id)
        await self._saleor.update_product(
            product_id=entry.saleor_product_id,
            name=product_name,
            slug=ProductSlug.for_candidate(candidate_id),
            category_id=None,
        )
        updated = entry.model_copy(update={'category_id': None})
        await self._entries.save_entry(updated)
        return updated

    async def _require_category(self, category_id: str) -> Category:
        category = await self._categories.by_id(category_id)
        if category is None:
            raise CategoryNotFoundError(f'category {category_id!r} was not found')
        return category

    async def _require_published_entry(self, candidate_id: str) -> CatalogueEntry:
        entry = await self._entries.by_candidate(candidate_id)
        if entry is None:
            raise CatalogueEntryNotFoundError(
                f'catalogue entry for candidate {candidate_id!r} was not found'
            )
        if entry.state is not CatalogueEntryState.PUBLISHED:
            raise CatalogueEntryNotPublishedError(
                f'catalogue entry for candidate {candidate_id!r} is not published'
            )
        return entry

    @staticmethod
    def _id_for(slug: str) -> str:
        return f'cat-{slug}'
