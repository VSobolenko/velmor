from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.errors import CheckoutRefusedError, DeliveryRefusedError
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
LATER = datetime(2026, 9, 20, 13, 0, tzinfo=timezone.utc)
BUYER_ID = 'buyer-1'
CANDIDATE_ID = 'openverse:1'
PROVIDER_ID = 'fake'
RETURN_URL = 'https://shop.example/return'
UNIT_AMOUNT = Decimal('12.50')
CURRENCY = 'BYN'
REFUND_REASON = 'payment refunded by operator'
PAYLOAD = b'entitled-asset-bytes'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
ORIGIN_URL = 'https://secret-origin.example/never-leak/asset.bin'


class FakePaymentProvider:
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


def build_entry() -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=CANDIDATE_ID,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=('credit the creator',),
        listing=StorefrontListing.PAID_OK,
        state=CatalogueEntryState.PUBLISHED,
        withdrawal_reason=None,
        published_at=NOW,
        content_digest=DIGEST,
        origin_url=ORIGIN_URL,
    )


def build_cart() -> Cart:
    return Cart(
        buyer_id=BUYER_ID,
        currency=CURRENCY,
        lines=(CartLine(candidate_id=CANDIDATE_ID, unit_amount=UNIT_AMOUNT, quantity=1),),
    )


def build_checkout(store: InMemoryStore, provider: FakePaymentProvider) -> CheckoutService:
    return CheckoutService(
        entries=store,
        disclosures=store,
        orders=store,
        entitlements=store,
        providers={provider.provider_id: provider},
    )


async def paid_order(store: InMemoryStore, provider: FakePaymentProvider) -> Order:
    await store.save_disclosure(build_disclosure())
    await store.save_entry(build_entry())
    service = build_checkout(store, provider)
    order, _payment = await service.start(build_cart(), PROVIDER_ID, RETURN_URL, NOW)
    return await service.confirm(
        PaymentConfirmation(
            provider_reference=order.provider_reference or '',
            order_id=order.order_id,
            amount=order.total,
            currency=order.currency,
            succeeded=True,
        ),
        NOW,
    )


_: PaymentProvider = FakePaymentProvider()


class TestRefund:
    async def test_refund_paid_order_revokes_and_refuses_delivery(
        self, tmp_path: Path
    ) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        order = await paid_order(store, provider)
        checkout = build_checkout(store, provider)

        refunded = await checkout.refund(order.order_id, REFUND_REASON, LATER)

        assert refunded.state is OrderState.REFUNDED
        rows = await store.for_buyer_candidate(BUYER_ID, CANDIDATE_ID)
        assert len(rows) == 1
        assert rows[0].state is EntitlementState.REVOKED
        assert rows[0].order_id == order.order_id
        assert rows[0].revoked_at == LATER
        assert rows[0].revocation_reason == REFUND_REASON

        origin_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal origin_calls
            origin_calls += 1
            return httpx.Response(200, content=PAYLOAD)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        cache.put(DIGEST, PAYLOAD)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            delivery = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            with pytest.raises(DeliveryRefusedError) as raised:
                await delivery.deliver(BUYER_ID, CANDIDATE_ID)

        assert REFUND_REASON in str(raised.value)
        assert origin_calls == 0

    async def test_second_order_for_same_good_stays_active(self) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        first = await paid_order(store, provider)
        second = await paid_order(store, provider)
        checkout = build_checkout(store, provider)

        await checkout.refund(first.order_id, REFUND_REASON, LATER)

        rows = await store.for_buyer_candidate(BUYER_ID, CANDIDATE_ID)
        by_order = {row.order_id: row for row in rows}
        assert by_order[first.order_id].state is EntitlementState.REVOKED
        assert by_order[second.order_id].state is EntitlementState.ACTIVE
        assert by_order[second.order_id].revocation_reason is None

    async def test_idempotent_refund_of_already_refunded(self) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        order = await paid_order(store, provider)
        checkout = build_checkout(store, provider)

        first = await checkout.refund(order.order_id, REFUND_REASON, LATER)
        second = await checkout.refund(order.order_id, 'another reason', LATER)

        assert first.state is OrderState.REFUNDED
        assert second.state is OrderState.REFUNDED
        rows = await store.for_buyer_candidate(BUYER_ID, CANDIDATE_ID)
        assert len(rows) == 1
        assert rows[0].state is EntitlementState.REVOKED
        assert rows[0].revocation_reason == REFUND_REASON

    async def test_refund_pending_is_refused(self) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        await store.save_disclosure(build_disclosure())
        await store.save_entry(build_entry())
        checkout = build_checkout(store, provider)
        order, _payment = await checkout.start(build_cart(), PROVIDER_ID, RETURN_URL, NOW)

        with pytest.raises(CheckoutRefusedError):
            await checkout.refund(order.order_id, REFUND_REASON, LATER)

        stored = await store.by_order_id(order.order_id)
        assert stored is not None
        assert stored.state is OrderState.PENDING
        assert await store.for_buyer_candidate(BUYER_ID, CANDIDATE_ID) == ()

    async def test_unknown_order_is_refused(self) -> None:
        store = InMemoryStore()
        provider = FakePaymentProvider()
        checkout = build_checkout(store, provider)

        with pytest.raises(CheckoutRefusedError):
            await checkout.refund('missing-order', REFUND_REASON, LATER)
