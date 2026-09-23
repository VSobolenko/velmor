from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.services.src.commerce.category_service import CategoryService
from packages.services.src.commerce.errors import (
    CatalogueEntryNotFoundError,
    CatalogueEntryNotPublishedError,
    CategoryNotEmptyError,
    CategoryNotFoundError,
    CategorySlugTakenError,
)
from packages.services.src.commerce.slugs import ProductSlug
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.category import CategoryName
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.presentation import Locale
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.saleor.client import SaleorCategory, SaleorProduct

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)
NAMES = (
    CategoryName(locale=Locale.RU, name='Фотографии'),
    CategoryName(locale=Locale.BE, name='Фатаграфіі'),
    CategoryName(locale=Locale.EN, name='Photographs'),
)
RENAMED_NAMES = (
    CategoryName(locale=Locale.RU, name='Изображения'),
    CategoryName(locale=Locale.BE, name='Выявы'),
    CategoryName(locale=Locale.EN, name='Images'),
)


class FakeSaleor:
    """Records Saleor category and product calls; returns stable ids."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self._category_seq = 0

    async def create_category(self, name: str, slug: str) -> SaleorCategory:
        self.calls.append(('create_category', name, slug))
        self._category_seq += 1
        return SaleorCategory(category_id=f'saleor-cat-{self._category_seq}')

    async def update_category(
        self, category_id: str, name: str, slug: str
    ) -> SaleorCategory:
        self.calls.append(('update_category', category_id, name, slug))
        return SaleorCategory(category_id=category_id)

    async def delete_category(self, category_id: str) -> None:
        self.calls.append(('delete_category', category_id))

    async def update_product(
        self, product_id: str, name: str, slug: str, category_id: str | None
    ) -> SaleorProduct:
        self.calls.append(('update_product', product_id, name, slug, category_id))
        return SaleorProduct(product_id=product_id)


def published_entry(
    candidate_id: str = 'openverse:1',
    category_id: str | None = None,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=category_id,
        license_id='CC-BY-4.0',
        obligations=('credit the creator',),
        listing=StorefrontListing.PAID_OK,
        state=CatalogueEntryState.PUBLISHED,
        withdrawal_reason=None,
        published_at=EARLIER,
        content_digest='00' * 32,
        origin_url='https://openverse.test/items/openverse:1.bin',
    )


def withdrawn_entry(candidate_id: str = 'openverse:1') -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=('credit the creator',),
        listing=StorefrontListing.PAID_OK,
        state=CatalogueEntryState.WITHDRAWN,
        withdrawal_reason='withdrawn for test',
        published_at=EARLIER,
        content_digest='00' * 32,
        origin_url='https://openverse.test/items/openverse:1.bin',
    )


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def saleor() -> FakeSaleor:
    return FakeSaleor()


@pytest.fixture
def service(store: InMemoryStore, saleor: FakeSaleor) -> CategoryService:
    return CategoryService(categories=store, entries=store, saleor=saleor)


class TestCreate:
    async def test_create_succeeds_and_round_trips(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        category = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)

        assert category.name == 'Photographs'
        assert category.slug == 'photographs'
        assert category.names == NAMES
        assert category.saleor_category_id == 'saleor-cat-1'
        assert category.created_at == NOW
        assert category.category_id == 'cat-photographs'
        assert await store.by_id(category.category_id) == category
        assert await store.by_slug('photographs') == category
        assert category in await store.all()
        assert saleor.calls == [('create_category', 'Photographs', 'photographs')]

    async def test_saleor_receives_one_name_while_every_name_is_stored(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        category = await service.create(
            name='Photographs', slug='photographs', names=NAMES, now=NOW
        )

        # The external catalogue node has exactly one name; the buyer-facing
        # names are ours and never travel to Saleor.
        assert [call for call in saleor.calls if call[0] == 'create_category'] == [
            ('create_category', 'Photographs', 'photographs')
        ]
        stored = await store.by_id(category.category_id)
        assert stored is not None
        assert stored.names == NAMES

    async def test_create_with_taken_slug_refuses_without_saleor(
        self, service: CategoryService, saleor: FakeSaleor
    ) -> None:
        await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        saleor.calls.clear()

        with pytest.raises(CategorySlugTakenError):
            await service.create(name='Photos', slug='photographs', names=NAMES, now=NOW)

        assert saleor.calls == []


class TestRename:
    async def test_rename_changes_name_and_slug(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        created = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        saleor.calls.clear()

        renamed = await service.rename(
            created.category_id,
            new_name='Images',
            new_slug='images',
            new_names=RENAMED_NAMES,
        )

        assert renamed.name == 'Images'
        assert renamed.slug == 'images'
        assert renamed.names == RENAMED_NAMES
        assert renamed.saleor_category_id == created.saleor_category_id
        assert await store.by_slug('photographs') is None
        assert await store.by_slug('images') == renamed
        assert saleor.calls == [
            ('update_category', created.saleor_category_id, 'Images', 'images')
        ]

    async def test_rename_that_collides_refuses_without_saleor(
        self, service: CategoryService, saleor: FakeSaleor
    ) -> None:
        first = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        await service.create(name='Audio', slug='audio', names=NAMES, now=NOW)
        saleor.calls.clear()

        with pytest.raises(CategorySlugTakenError):
            await service.rename(
                first.category_id,
                new_name='Sound',
                new_slug='audio',
                new_names=RENAMED_NAMES,
            )

        assert saleor.calls == []

    async def test_rename_that_keeps_the_same_slug_succeeds(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        created = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        saleor.calls.clear()

        renamed = await service.rename(
            created.category_id,
            new_name='Photos',
            new_slug='photographs',
            new_names=RENAMED_NAMES,
        )

        assert renamed.name == 'Photos'
        assert renamed.slug == 'photographs'
        assert await store.by_slug('photographs') == renamed
        assert saleor.calls == [
            ('update_category', created.saleor_category_id, 'Photos', 'photographs')
        ]


class TestRemove:
    async def test_remove_empty_category_deletes_in_saleor_and_store(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        created = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        saleor.calls.clear()

        await service.remove(created.category_id)

        assert await store.by_id(created.category_id) is None
        assert saleor.calls == [('delete_category', created.saleor_category_id)]

    async def test_remove_non_empty_category_refuses_without_saleor(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        created = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        await store.save_entry(
            published_entry(candidate_id='openverse:a', category_id=created.category_id)
        )
        await store.save_entry(
            published_entry(candidate_id='openverse:b', category_id=created.category_id)
        )
        saleor.calls.clear()

        with pytest.raises(CategoryNotEmptyError) as raised:
            await service.remove(created.category_id)

        assert raised.value.blocking_candidate_ids == ('openverse:a', 'openverse:b')
        assert saleor.calls == []
        assert await store.by_id(created.category_id) == created

    async def test_remove_unknown_category_raises(
        self, service: CategoryService, saleor: FakeSaleor
    ) -> None:
        with pytest.raises(CategoryNotFoundError):
            await service.remove('cat-missing')

        assert saleor.calls == []


class TestAssign:
    async def test_assign_sets_category_on_published_entry(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        category = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        await store.save_entry(published_entry(candidate_id='openverse:1'))
        saleor.calls.clear()

        updated = await service.assign(
            candidate_id='openverse:1',
            category_id=category.category_id,
            product_name='Lantern photograph',
        )

        assert updated.category_id == category.category_id
        assert await store.by_category(category.category_id) == (updated,)
        assert saleor.calls == [
            (
                'update_product',
                'product-1',
                'Lantern photograph',
                ProductSlug.for_candidate('openverse:1'),
                category.saleor_category_id,
            )
        ]

    async def test_assign_missing_entry_refuses_without_saleor(
        self, service: CategoryService, saleor: FakeSaleor
    ) -> None:
        category = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        saleor.calls.clear()

        with pytest.raises(CatalogueEntryNotFoundError):
            await service.assign('missing', category.category_id, 'Title')

        assert saleor.calls == []

    async def test_assign_missing_category_refuses_without_saleor(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        await store.save_entry(published_entry())
        saleor.calls.clear()

        with pytest.raises(CategoryNotFoundError):
            await service.assign('openverse:1', 'cat-missing', 'Title')

        assert saleor.calls == []

    async def test_assign_withdrawn_entry_refuses_without_saleor(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        category = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        await store.save_entry(withdrawn_entry())
        saleor.calls.clear()

        with pytest.raises(CatalogueEntryNotPublishedError):
            await service.assign('openverse:1', category.category_id, 'Title')

        assert saleor.calls == []


class TestUnassign:
    async def test_unassign_clears_category(
        self, service: CategoryService, store: InMemoryStore, saleor: FakeSaleor
    ) -> None:
        category = await service.create(name='Photographs', slug='photographs', names=NAMES, now=NOW)
        await store.save_entry(
            published_entry(candidate_id='openverse:1', category_id=category.category_id)
        )
        saleor.calls.clear()

        updated = await service.unassign(
            candidate_id='openverse:1', product_name='Lantern photograph'
        )

        assert updated.category_id is None
        assert await store.by_category(category.category_id) == ()
        assert saleor.calls == [
            (
                'update_product',
                'product-1',
                'Lantern photograph',
                ProductSlug.for_candidate('openverse:1'),
                None,
            )
        ]
