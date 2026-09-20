from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.services.src.domain.order import Order, OrderLine, OrderState
from packages.services.src.persistence.contract import OrderRepository
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.persistence.postgres import PostgresStore

CREATED_AT = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
UNCONNECTED_DSN = 'postgresql+asyncpg://localhost/velmor'


def build_order(
    order_id: str = 'order-1',
    *,
    provider_id: str | None = 'fake',
    provider_reference: str | None = 'ref-1',
    state: OrderState = OrderState.PENDING,
) -> Order:
    line = OrderLine(
        candidate_id='openverse:1',
        unit_amount=Decimal('10.00'),
        quantity=1,
    )
    return Order(
        order_id=order_id,
        buyer_id='buyer-1',
        state=state,
        currency='BYN',
        lines=(line,),
        total=Decimal('10.00'),
        provider_id=provider_id,
        provider_reference=provider_reference,
        created_at=CREATED_AT,
        paid_at=None,
    )


class TestOrderRepository:
    async def test_an_order_round_trips_by_id(self) -> None:
        store = InMemoryStore()
        order = build_order()

        await store.save_order(order)

        assert await store.by_id('order-1') == order

    async def test_by_provider_reference_finds_the_order(self) -> None:
        store = InMemoryStore()
        order = build_order()
        await store.save_order(order)

        assert await store.by_provider_reference('fake', 'ref-1') == order
        assert await store.by_provider_reference('fake', 'missing') is None
        assert await store.by_provider_reference('other', 'ref-1') is None

    async def test_save_order_replaces_by_order_id(self) -> None:
        store = InMemoryStore()
        await store.save_order(build_order())
        paid = build_order(state=OrderState.PAID).model_copy(
            update={'paid_at': CREATED_AT}
        )

        await store.save_order(paid)

        assert await store.by_id('order-1') == paid
        assert await store.by_provider_reference('fake', 'ref-1') == paid

    async def test_order_without_provider_reference_is_not_indexed(self) -> None:
        store = InMemoryStore()
        order = build_order(provider_id=None, provider_reference=None)
        await store.save_order(order)

        assert await store.by_id('order-1') == order
        assert await store.by_provider_reference('fake', 'ref-1') is None


class TestOrderRepositoryConformance:
    def test_the_in_memory_store_satisfies_order_repository(self) -> None:
        assert isinstance(InMemoryStore(), OrderRepository)

    async def test_the_postgres_store_satisfies_order_repository(self) -> None:
        engine = create_async_engine(UNCONNECTED_DSN)
        store = PostgresStore(engine, async_sessionmaker(engine, expire_on_commit=False))

        assert isinstance(store, OrderRepository)

        await engine.dispose()

    def test_a_class_missing_a_method_does_not_satisfy_the_protocol(self) -> None:
        class Incomplete:
            async def save_order(self, order: Order) -> None: ...

            async def by_id(self, order_id: str) -> Order | None: ...

        assert not isinstance(Incomplete(), OrderRepository)
