from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.services.src.commerce.disclosure import SellerDisclosureCheck
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.category import Category
from packages.services.src.domain.entitlement import Entitlement, EntitlementState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.seller import SellerDisclosure, SellerDisclosureItem
from packages.services.src.persistence.contract import (
    CatalogueEntryRepository,
    CategoryRepository,
    EntitlementRepository,
    SellerDisclosureRepository,
)
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.persistence.postgres import PostgresStore

PUBLISHED_AT = datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc)
GRANTED_AT = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
CATEGORY_CREATED_AT = datetime(2026, 9, 20, 8, 0, tzinfo=timezone.utc)

# A DSN with no credentials and no server behind it. ``create_async_engine``
# builds the engine lazily and never connects, which is what lets the
# conformance check construct ``PostgresStore`` without a database.
UNCONNECTED_DSN = 'postgresql+asyncpg://localhost/velmor'

# Written out rather than read from ``SellerDisclosureCheck.REQUIRED_ITEMS``, so
# the check is compared against the requirement and not against itself.
ALL_DISCLOSURE_ITEMS: tuple[SellerDisclosureItem, ...] = (
    SellerDisclosureItem.LEGAL_NAME,
    SellerDisclosureItem.REGISTRATION_NUMBER,
    SellerDisclosureItem.REGISTRATION_DATE,
    SellerDisclosureItem.REGISTRATION_AUTHORITY,
    SellerDisclosureItem.SHOP_REGISTER_NUMBER,
    SellerDisclosureItem.POSTAL_ADDRESS,
    SellerDisclosureItem.WORKING_HOURS,
    SellerDisclosureItem.CONTACT_DETAILS,
    SellerDisclosureItem.PAYMENT_RULES,
    SellerDisclosureItem.RETURN_RULES,
    SellerDisclosureItem.PAYMENT_SYSTEM_MARKS,
)


def build_entry(
    candidate_id: str = 'openverse:1',
    category_id: str | None = 'images',
    state: CatalogueEntryState = CatalogueEntryState.PUBLISHED,
    withdrawal_reason: str | None = None,
    published_at: datetime = PUBLISHED_AT,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id='UHJvZHVjdDox',
        saleor_variant_id='UHJvZHVjdFZhcmlhbnQ6MQ==',
        category_id=category_id,
        license_id='CC-BY-4.0',
        obligations=('credit the creator',),
        listing=StorefrontListing.PAID_OK,
        state=state,
        withdrawal_reason=withdrawal_reason,
        published_at=published_at,
        content_digest='00' * 32,
        origin_url='https://openverse.test/items/openverse:1.bin',
    )


def build_entitlement(
    buyer_id: str = 'buyer-1',
    candidate_id: str = 'openverse:1',
    order_id: str = 'order-1',
    state: EntitlementState = EntitlementState.ACTIVE,
    granted_at: datetime = GRANTED_AT,
    revoked_at: datetime | None = None,
    revocation_reason: str | None = None,
) -> Entitlement:
    return Entitlement(
        buyer_id=buyer_id,
        candidate_id=candidate_id,
        order_id=order_id,
        granted_at=granted_at,
        state=state,
        revoked_at=revoked_at,
        revocation_reason=revocation_reason,
    )


def build_disclosure(
    legal_name: str | None = 'Velmor LLC',
) -> SellerDisclosure:
    return SellerDisclosure(
        legal_name=legal_name,
        registration_number='100200300',
        registration_date=datetime(2026, 1, 15, tzinfo=timezone.utc).date(),
        registration_authority='Minsk City Executive Committee',
        shop_register_number='SHOP-1',
        postal_address='Minsk, Belarus',
        working_hours='Mon-Fri 09:00-18:00',
        contact_details='support@velmor.example',
        payment_rules='Payment by card at checkout',
        return_rules='Digital goods are not returnable after download',
        payment_system_marks=('visa', 'mastercard'),
    )


def build_category(
    category_id: str = 'cat-photographs',
    name: str = 'Photographs',
    slug: str = 'photographs',
    saleor_category_id: str = 'saleor-cat-1',
    created_at: datetime = CATEGORY_CREATED_AT,
) -> Category:
    return Category(
        category_id=category_id,
        name=name,
        slug=slug,
        saleor_category_id=saleor_category_id,
        created_at=created_at,
    )


class TestCategoryRepository:
    async def test_a_category_round_trips_by_id_and_slug(self) -> None:
        store = InMemoryStore()
        category = build_category()

        await store.save_category(category)

        assert await store.by_id('cat-photographs') == category
        assert await store.by_slug('photographs') == category

    async def test_all_orders_by_name_then_category_id(self) -> None:
        store = InMemoryStore()
        zebra = build_category(category_id='cat-zebra', name='Zebra', slug='zebra')
        apple_b = build_category(category_id='cat-apple-b', name='Apple', slug='apple-b')
        apple_a = build_category(category_id='cat-apple-a', name='Apple', slug='apple-a')
        for category in (zebra, apple_b, apple_a):
            await store.save_category(category)

        assert await store.all() == (apple_a, apple_b, zebra)

    async def test_save_category_replaces_by_category_id(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())
        renamed = build_category(name='Photos', slug='photos')

        await store.save_category(renamed)

        assert await store.by_id('cat-photographs') == renamed
        assert await store.by_slug('photos') == renamed
        assert await store.by_slug('photographs') is None

    async def test_delete_category_removes_the_row(self) -> None:
        store = InMemoryStore()
        await store.save_category(build_category())

        await store.delete_category('cat-photographs')

        assert await store.by_id('cat-photographs') is None
        assert await store.by_slug('photographs') is None
        assert await store.all() == ()

    async def test_delete_category_of_a_missing_id_is_a_noop(self) -> None:
        store = InMemoryStore()

        await store.delete_category('cat-missing')

        assert await store.all() == ()


class TestCatalogueEntryRepository:
    async def test_an_entry_round_trips_whole(self) -> None:
        store = InMemoryStore()
        entry = build_entry()

        await store.save_entry(entry)

        assert await store.by_candidate('openverse:1') == entry

    async def test_a_withdrawal_replaces_the_published_entry(self) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        withdrawn = build_entry().model_copy(
            update={
                'state': CatalogueEntryState.WITHDRAWN,
                'withdrawal_reason': 'the decision is no longer publishable',
            }
        )

        await store.save_entry(withdrawn)

        stored = await store.by_candidate('openverse:1')
        assert stored is not None
        assert stored == withdrawn
        assert stored.withdrawal_reason == 'the decision is no longer publishable'
        assert await store.entries(10) == (withdrawn,)

    async def test_an_unknown_good_has_no_entry(self) -> None:
        store = InMemoryStore()

        assert await store.by_candidate('openverse:missing') is None

    async def test_a_category_returns_only_its_own_entries(self) -> None:
        store = InMemoryStore()
        image = build_entry(candidate_id='openverse:image', category_id='images')
        audio = build_entry(candidate_id='openverse:audio', category_id='audio')
        await store.save_entry(image)
        await store.save_entry(audio)

        assert await store.by_category('images') == (image,)

    async def test_a_category_with_no_entries_is_empty(self) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry(category_id='images'))

        assert await store.by_category('audio') == ()

    async def test_entries_are_most_recent_first_and_respect_the_limit(self) -> None:
        store = InMemoryStore()
        oldest = build_entry(candidate_id='openverse:1', published_at=PUBLISHED_AT)
        middle = build_entry(
            candidate_id='openverse:2', published_at=PUBLISHED_AT + timedelta(hours=1)
        )
        newest = build_entry(
            candidate_id='openverse:3', published_at=PUBLISHED_AT + timedelta(hours=2)
        )
        for entry in (middle, oldest, newest):
            await store.save_entry(entry)

        assert await store.entries(2) == (newest, middle)
        assert await store.entries(10) == (newest, middle, oldest)

    async def test_entries_sharing_a_timestamp_are_ordered_by_candidate_id(self) -> None:
        store = InMemoryStore()
        second = build_entry(candidate_id='openverse:2')
        first = build_entry(candidate_id='openverse:1')
        await store.save_entry(second)
        await store.save_entry(first)

        assert await store.entries(10) == (first, second)
        assert await store.by_category('images') == (first, second)


class TestEntitlementRepository:
    async def test_an_entitlement_round_trips_whole(self) -> None:
        store = InMemoryStore()
        entitlement = build_entitlement()

        await store.save_entitlement(entitlement)

        assert await store.for_buyer_candidate('buyer-1', 'openverse:1') == (entitlement,)

    async def test_two_orders_for_one_good_hold_two_entitlements(self) -> None:
        store = InMemoryStore()
        first = build_entitlement(order_id='order-1')
        second = build_entitlement(
            order_id='order-2', granted_at=GRANTED_AT + timedelta(days=1)
        )
        await store.save_entitlement(first)
        await store.save_entitlement(second)

        stored = await store.for_buyer_candidate('buyer-1', 'openverse:1')

        assert len(stored) == 2
        assert stored == (second, first)

    async def test_a_revoked_entitlement_is_still_returned_with_its_reason(self) -> None:
        store = InMemoryStore()
        revoked = build_entitlement(
            state=EntitlementState.REVOKED,
            revoked_at=GRANTED_AT + timedelta(days=1),
            revocation_reason='the order was refunded',
        )
        await store.save_entitlement(revoked)

        stored = await store.for_buyer_candidate('buyer-1', 'openverse:1')

        assert stored == (revoked,)
        assert stored[0].state is EntitlementState.REVOKED
        assert stored[0].revocation_reason == 'the order was refunded'

    async def test_revoking_replaces_the_entitlement_of_that_order(self) -> None:
        store = InMemoryStore()
        await store.save_entitlement(build_entitlement(order_id='order-1'))
        revoked = build_entitlement(
            order_id='order-1',
            state=EntitlementState.REVOKED,
            revoked_at=GRANTED_AT + timedelta(days=1),
            revocation_reason='the order was refunded',
        )

        await store.save_entitlement(revoked)

        assert await store.for_buyer_candidate('buyer-1', 'openverse:1') == (revoked,)

    async def test_for_buyer_returns_only_that_buyers_entitlements(self) -> None:
        store = InMemoryStore()
        mine = build_entitlement(buyer_id='buyer-1', order_id='order-1')
        other = build_entitlement(buyer_id='buyer-2', order_id='order-2')
        await store.save_entitlement(mine)
        await store.save_entitlement(other)

        assert await store.for_buyer('buyer-1') == (mine,)

    async def test_for_buyer_is_most_recently_granted_first(self) -> None:
        store = InMemoryStore()
        older = build_entitlement(
            candidate_id='openverse:1', order_id='order-1', granted_at=GRANTED_AT
        )
        newer = build_entitlement(
            candidate_id='openverse:2',
            order_id='order-2',
            granted_at=GRANTED_AT + timedelta(days=1),
        )
        await store.save_entitlement(older)
        await store.save_entitlement(newer)

        assert await store.for_buyer('buyer-1') == (newer, older)

    async def test_a_buyer_who_never_bought_the_good_has_no_entitlement(self) -> None:
        store = InMemoryStore()
        await store.save_entitlement(build_entitlement(candidate_id='openverse:1'))

        assert await store.for_buyer_candidate('buyer-1', 'openverse:other') == ()


class TestSellerDisclosureRepository:
    async def test_current_is_none_before_a_disclosure_is_saved(self) -> None:
        store = InMemoryStore()

        assert await store.current() is None

    async def test_a_disclosure_round_trips_whole(self) -> None:
        store = InMemoryStore()
        disclosure = build_disclosure()

        await store.save_disclosure(disclosure)

        assert await store.current() == disclosure

    async def test_a_second_disclosure_replaces_the_first(self) -> None:
        store = InMemoryStore()
        first = build_disclosure(legal_name='First Seller')
        second = build_disclosure(legal_name='Second Seller')
        await store.save_disclosure(first)

        assert await store.current() == first

        await store.save_disclosure(second)

        assert await store.current() == second

    async def test_an_empty_disclosure_round_trips_as_incomplete(self) -> None:
        store = InMemoryStore()
        await store.save_disclosure(SellerDisclosure())

        disclosure = await store.current()

        assert disclosure == SellerDisclosure()
        assert SellerDisclosureCheck().incomplete(disclosure) == ALL_DISCLOSURE_ITEMS
        assert len(SellerDisclosureCheck().incomplete(disclosure)) == 11

    def test_an_empty_string_would_read_as_configured(self) -> None:
        """Why the round trip above has to keep ``None`` as ``None``.

        The completeness check asks ``is None``, so an empty string counts as a
        configured value: the same fully populated disclosure with ``''`` for
        ``legal_name`` reports nothing missing at all. Had the store mapped an
        absent item to ``''``, that item would drop out of the missing list and
        ``test_an_empty_disclosure_round_trips_as_incomplete`` would fail.
        """
        check = SellerDisclosureCheck()
        disclosure = build_disclosure(legal_name='')

        assert disclosure.legal_name == ''
        assert SellerDisclosureItem.LEGAL_NAME not in check.incomplete(disclosure)
        assert check.incomplete(disclosure) == ()


class _IncompleteCatalogueEntryRepository:
    """Implements three of the four ``CatalogueEntryRepository`` methods."""

    async def save_entry(self, entry: CatalogueEntry) -> None: ...

    async def by_candidate(self, candidate_id: str) -> CatalogueEntry | None: ...

    async def by_category(self, category_id: str) -> tuple[CatalogueEntry, ...]: ...


class _IncompleteCategoryRepository:
    """Implements four of the five ``CategoryRepository`` methods."""

    async def save_category(self, category: Category) -> None: ...

    async def by_id(self, category_id: str) -> Category | None: ...

    async def by_slug(self, slug: str) -> Category | None: ...

    async def all(self) -> tuple[Category, ...]: ...


class _IncompleteEntitlementRepository:
    """Implements two of the three ``EntitlementRepository`` methods."""

    async def save_entitlement(self, entitlement: Entitlement) -> None: ...

    async def for_buyer(self, buyer_id: str) -> tuple[Entitlement, ...]: ...


class _IncompleteSellerDisclosureRepository:
    """Implements one of the two ``SellerDisclosureRepository`` methods."""

    async def save_disclosure(self, disclosure: SellerDisclosure) -> None: ...


class TestRepositoryConformance:
    """Both stores expose every new protocol's methods.

    ``@runtime_checkable`` ``isinstance`` answers one question: does an
    attribute of that name exist. It does not check signatures, so a method with
    the wrong parameters satisfies it and fails at runtime, and it is satisfied
    by a name a second definition shadows, which is why the three write methods
    are named after their subjects rather than all being ``save``. This test
    catches a method that is missing or renamed; the round-trip tests above are
    what guard the behaviour.
    """

    def test_the_in_memory_store_satisfies_every_commerce_protocol(self) -> None:
        store = InMemoryStore()

        assert isinstance(store, CatalogueEntryRepository)
        assert isinstance(store, CategoryRepository)
        assert isinstance(store, EntitlementRepository)
        assert isinstance(store, SellerDisclosureRepository)

    async def test_the_postgres_store_satisfies_every_commerce_protocol(self) -> None:
        engine = create_async_engine(UNCONNECTED_DSN)
        store = PostgresStore(engine, async_sessionmaker(engine, expire_on_commit=False))

        assert isinstance(store, CatalogueEntryRepository)
        assert isinstance(store, CategoryRepository)
        assert isinstance(store, EntitlementRepository)
        assert isinstance(store, SellerDisclosureRepository)

        await engine.dispose()

    def test_a_class_missing_a_method_does_not_satisfy_the_protocol(self) -> None:
        assert not isinstance(
            _IncompleteCatalogueEntryRepository(), CatalogueEntryRepository
        )
        assert not isinstance(_IncompleteCategoryRepository(), CategoryRepository)
        assert not isinstance(_IncompleteEntitlementRepository(), EntitlementRepository)
        assert not isinstance(
            _IncompleteSellerDisclosureRepository(), SellerDisclosureRepository
        )
