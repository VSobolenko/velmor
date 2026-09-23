from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.errors import CheckoutRefusedError
from packages.services.src.domain.cart import Cart, CartLine
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.entitlement import EntitlementState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.order import Order, OrderState
from packages.services.src.domain.seller import SellerDisclosure
from packages.services.src.payments.protocol import (
    PaymentConfirmation,
    PaymentProvider,
    PaymentStart,
)
from packages.services.src.persistence.memory import InMemoryStore

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
BUYER_ID = 'buyer-1'
CANDIDATE_A = 'openverse:1'
CANDIDATE_B = 'openverse:2'
PROVIDER_ID = 'fake'
RETURN_URL = 'https://shop.example/return'
UNIT_AMOUNT = Decimal('12.50')
CURRENCY = 'USD'


class FakePaymentProvider:
    """Hand-written double that records every start_payment call."""

    def __init__(self, provider_id: str = PROVIDER_ID) -> None:
        self._provider_id = provider_id
        self.started: list[tuple[Order, str]] = []

    @property
    def provider_id(self) -> str:
        return self._provider_id

    async def start_payment(self, order: Order, return_url: str) -> PaymentStart:
        self.started.append((order, return_url))
        return PaymentStart(
            redirect_url=f'https://pay.example/{order.order_id}',
            provider_reference=f'ref-{order.order_id}',
        )


def build_disclosure() -> SellerDisclosure:
    return SellerDisclosure(
        legal_name='Velmor LLC',
        registration_number='100200300',
        registration_date=date(2026, 1, 15),
        registration_authority='Minsk City Executive Committee',
        shop_register_number='SHOP-1',
        postal_address='Minsk, Belarus',
        working_hours='Mon-Fri 09:00-18:00',
        contact_details='support@velmor.example',
        payment_rules='Payment by card at checkout',
        return_rules='Digital goods are not returnable after download',
        payment_system_marks=('visa', 'mastercard'),
    )


def build_entry(
    candidate_id: str = CANDIDATE_A,
    *,
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
        obligations=('credit the creator',),
        listing=listing,
        state=state,
        withdrawal_reason='withdrawn for test' if state is CatalogueEntryState.WITHDRAWN else None,
        published_at=NOW,
        content_digest='00' * 32,
        origin_url=f'https://openverse.test/items/{candidate_id}.bin',
    )


def build_cart(
    *candidate_ids: str,
    unit_amount: Decimal = UNIT_AMOUNT,
    quantity: int = 1,
    currency: str = CURRENCY,
) -> Cart:
    lines = tuple(
        CartLine(candidate_id=candidate_id, unit_amount=unit_amount, quantity=quantity)
        for candidate_id in candidate_ids
    )
    return Cart(buyer_id=BUYER_ID, currency=currency, lines=lines)


def build_service(
    store: InMemoryStore,
    provider: FakePaymentProvider,
) -> CheckoutService:
    return CheckoutService(
        entries=store,
        disclosures=store,
        orders=store,
        entitlements=store,
        providers={provider.provider_id: provider},
    )


class TestCheckoutStart:
    async def test_happy_start_creates_pending_order_and_redirect(self) -> None:
        store = InMemoryStore()
        await store.save_disclosure(build_disclosure())
        await store.save_entry(build_entry(CANDIDATE_A))
        await store.save_entry(build_entry(CANDIDATE_B))
        provider = FakePaymentProvider()
        service = build_service(store, provider)
        cart = build_cart(CANDIDATE_A, CANDIDATE_B)

        order, payment = await service.start(cart, PROVIDER_ID, RETURN_URL, NOW)

        assert order.state is OrderState.PENDING
        assert order.buyer_id == BUYER_ID
        assert order.currency == CURRENCY
        assert order.total == UNIT_AMOUNT * 2
        assert order.provider_id == PROVIDER_ID
        assert order.provider_reference == f'ref-{order.order_id}'
        assert order.created_at == NOW
        assert order.paid_at is None
        assert payment.redirect_url == f'https://pay.example/{order.order_id}'
        assert payment.provider_reference == order.provider_reference
        assert len(provider.started) == 1
        started_order, return_url = provider.started[0]
        assert return_url == RETURN_URL
        assert started_order.total == order.total
        assert started_order.currency == CURRENCY
        assert await store.by_order_id(order.order_id) == order

    async def test_incomplete_disclosure_refuses_without_calling_provider(self) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        provider = FakePaymentProvider()
        service = build_service(store, provider)

        with pytest.raises(CheckoutRefusedError) as raised:
            await service.start(build_cart(CANDIDATE_A), PROVIDER_ID, RETURN_URL, NOW)

        message = str(raised.value)
        assert 'legal_name' in message
        assert provider.started == []
        assert store.order_ids() == ()

    async def test_free_only_line_is_refused_naming_candidate_and_listing(self) -> None:
        store = InMemoryStore()
        await store.save_disclosure(build_disclosure())
        await store.save_entry(build_entry(listing=StorefrontListing.FREE_ONLY))
        provider = FakePaymentProvider()
        service = build_service(store, provider)

        with pytest.raises(CheckoutRefusedError) as raised:
            await service.start(build_cart(CANDIDATE_A), PROVIDER_ID, RETURN_URL, NOW)

        message = str(raised.value)
        assert CANDIDATE_A in message
        assert StorefrontListing.FREE_ONLY.value in message
        assert provider.started == []
        assert store.order_ids() == ()

    async def test_withdrawn_entry_is_refused(self) -> None:
        store = InMemoryStore()
        await store.save_disclosure(build_disclosure())
        await store.save_entry(build_entry(state=CatalogueEntryState.WITHDRAWN))
        provider = FakePaymentProvider()
        service = build_service(store, provider)

        with pytest.raises(CheckoutRefusedError) as raised:
            await service.start(build_cart(CANDIDATE_A), PROVIDER_ID, RETURN_URL, NOW)

        assert CANDIDATE_A in str(raised.value)
        assert provider.started == []
        assert store.order_ids() == ()

    async def test_missing_catalogue_entry_is_refused(self) -> None:
        store = InMemoryStore()
        await store.save_disclosure(build_disclosure())
        provider = FakePaymentProvider()
        service = build_service(store, provider)

        with pytest.raises(CheckoutRefusedError) as raised:
            await service.start(build_cart(CANDIDATE_A), PROVIDER_ID, RETURN_URL, NOW)

        assert CANDIDATE_A in str(raised.value)
        assert provider.started == []
        assert store.order_ids() == ()

    async def test_empty_cart_is_refused(self) -> None:
        store = InMemoryStore()
        await store.save_disclosure(build_disclosure())
        provider = FakePaymentProvider()
        service = build_service(store, provider)
        cart = Cart(buyer_id=BUYER_ID, currency=CURRENCY, lines=())

        with pytest.raises(CheckoutRefusedError):
            await service.start(cart, PROVIDER_ID, RETURN_URL, NOW)

        assert provider.started == []
        assert store.order_ids() == ()


class TestCheckoutConfirm:
    async def _started_order(
        self,
        store: InMemoryStore,
        provider: FakePaymentProvider,
        *candidate_ids: str,
    ) -> Order:
        await store.save_disclosure(build_disclosure())
        for candidate_id in candidate_ids:
            await store.save_entry(build_entry(candidate_id))
        service = build_service(store, provider)
        order, _payment = await service.start(
            build_cart(*candidate_ids), PROVIDER_ID, RETURN_URL, NOW
        )
        return order

    async def test_confirm_success_marks_paid_and_creates_entitlements(self) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        order = await self._started_order(store, provider, CANDIDATE_A, CANDIDATE_B)
        service = build_service(store, provider)
        confirmation = PaymentConfirmation(
            provider_reference=order.provider_reference or '',
            order_id=order.order_id,
            amount=order.total,
            currency=order.currency,
            succeeded=True,
        )

        paid = await service.confirm(confirmation, NOW)

        assert paid.state is OrderState.PAID
        assert paid.paid_at == NOW
        assert paid.total == order.total
        for candidate_id in (CANDIDATE_A, CANDIDATE_B):
            rows = await store.for_buyer_candidate(BUYER_ID, candidate_id)
            assert len(rows) == 1
            assert rows[0].state is EntitlementState.ACTIVE
            assert rows[0].order_id == order.order_id
            assert rows[0].granted_at == NOW

    async def test_confirm_repeated_keeps_one_entitlement_and_total(self) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        order = await self._started_order(store, provider, CANDIDATE_A)
        service = build_service(store, provider)
        confirmation = PaymentConfirmation(
            provider_reference=order.provider_reference or '',
            order_id=order.order_id,
            amount=order.total,
            currency=order.currency,
            succeeded=True,
        )

        first = await service.confirm(confirmation, NOW)
        second = await service.confirm(confirmation, NOW)

        assert first.state is OrderState.PAID
        assert second.state is OrderState.PAID
        assert second.total == first.total
        rows = await store.for_buyer_candidate(BUYER_ID, CANDIDATE_A)
        assert len(rows) == 1
        assert rows[0].state is EntitlementState.ACTIVE

    async def test_confirm_amount_mismatch_refuses_without_paying(self) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        order = await self._started_order(store, provider, CANDIDATE_A)
        service = build_service(store, provider)
        confirmation = PaymentConfirmation(
            provider_reference=order.provider_reference or '',
            order_id=order.order_id,
            amount=order.total + Decimal('1.00'),
            currency=order.currency,
            succeeded=True,
        )

        with pytest.raises(CheckoutRefusedError):
            await service.confirm(confirmation, NOW)

        stored = await store.by_order_id(order.order_id)
        assert stored is not None
        assert stored.state is OrderState.PENDING
        assert await store.for_buyer_candidate(BUYER_ID, CANDIDATE_A) == ()

    async def test_confirm_failed_marks_failed_without_entitlement(self) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        order = await self._started_order(store, provider, CANDIDATE_A)
        service = build_service(store, provider)
        confirmation = PaymentConfirmation(
            provider_reference=order.provider_reference or '',
            order_id=order.order_id,
            amount=order.total,
            currency=order.currency,
            succeeded=False,
        )

        failed = await service.confirm(confirmation, NOW)

        assert failed.state is OrderState.FAILED
        assert failed.paid_at is None
        assert await store.for_buyer_candidate(BUYER_ID, CANDIDATE_A) == ()


# Satisfy the type checker that FakePaymentProvider matches the protocol shape.
_: PaymentProvider = FakePaymentProvider()
