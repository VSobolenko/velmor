from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from packages.services.src.commerce.disclosure import SellerDisclosureCheck
from packages.services.src.commerce.errors import CheckoutRefusedError
from packages.services.src.domain.cart import Cart, CartLine
from packages.services.src.domain.catalogue import CatalogueEntryState
from packages.services.src.domain.entitlement import Entitlement, EntitlementState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.order import Order, OrderLine, OrderState
from packages.services.src.payments.protocol import (
    PaymentConfirmation,
    PaymentProvider,
    PaymentStart,
)
from packages.services.src.persistence.contract import (
    CatalogueEntryRepository,
    EntitlementRepository,
    OrderRepository,
    SellerDisclosureRepository,
)


class CheckoutService:
    """Start and confirm payment after re-verifying saleability at payment time.

    Design D9: Saleor is not the authority. Re-verification uses the catalogue
    entry's stored ``listing`` and ``state`` (``PAID_OK`` and ``PUBLISHED``).
    Design D7: incomplete seller disclosure refuses before any provider call.
    """

    def __init__(
        self,
        entries: CatalogueEntryRepository,
        disclosures: SellerDisclosureRepository,
        orders: OrderRepository,
        entitlements: EntitlementRepository,
        providers: dict[str, PaymentProvider],
    ) -> None:
        self._entries = entries
        self._disclosures = disclosures
        self._orders = orders
        self._entitlements = entitlements
        self._providers = providers
        self._disclosure_check = SellerDisclosureCheck()

    async def start(
        self,
        cart: Cart,
        provider_id: str,
        return_url: str,
        now: datetime,
    ) -> tuple[Order, PaymentStart]:
        await self._require_complete_disclosure()
        self._require_non_empty_cart(cart)
        self._require_valid_totals(cart)
        await self._require_saleable_lines(cart)
        provider = self._require_provider(provider_id)
        order = self._pending_order(cart, now)
        payment = await provider.start_payment(order, return_url)
        started = order.model_copy(
            update={
                'provider_id': provider_id,
                'provider_reference': payment.provider_reference,
            }
        )
        await self._orders.save_order(started)
        return started, payment

    async def confirm(self, confirmation: PaymentConfirmation, now: datetime) -> Order:
        order = await self._orders.by_id(confirmation.order_id)
        if order is None:
            raise CheckoutRefusedError(
                f'order {confirmation.order_id} is unknown'
            )
        if confirmation.amount != order.total or confirmation.currency != order.currency:
            raise CheckoutRefusedError(
                f'confirmation amount or currency does not match order {order.order_id}'
            )
        if not confirmation.succeeded:
            return await self._mark_failed(order)
        if order.state is OrderState.PAID:
            return self._idempotent_or_conflict(order, confirmation)
        if (
            order.provider_reference is not None
            and confirmation.provider_reference != order.provider_reference
        ):
            raise CheckoutRefusedError(
                f'confirmation reference does not match order {order.order_id}'
            )
        paid = order.model_copy(
            update={
                'state': OrderState.PAID,
                'paid_at': now,
                'provider_reference': confirmation.provider_reference,
            }
        )
        await self._orders.save_order(paid)
        await self._grant_entitlements(paid, now)
        return paid

    async def _require_complete_disclosure(self) -> None:
        missing = self._disclosure_check.incomplete(await self._disclosures.current())
        if missing == ():
            return
        names = ', '.join(item.value for item in missing)
        raise CheckoutRefusedError(
            f'seller disclosure is incomplete; missing: {names}'
        )

    @staticmethod
    def _require_non_empty_cart(cart: Cart) -> None:
        if cart.lines == ():
            raise CheckoutRefusedError('cart is empty')

    @staticmethod
    def _require_valid_totals(cart: Cart) -> None:
        if cart.currency == '':
            raise CheckoutRefusedError('currency is required')
        for line in cart.lines:
            if line.quantity < 1:
                raise CheckoutRefusedError(
                    f'quantity for {line.candidate_id} must be at least 1'
                )

    async def _require_saleable_lines(self, cart: Cart) -> None:
        for line in cart.lines:
            await self._require_saleable_line(line)

    async def _require_saleable_line(self, line: CartLine) -> None:
        entry = await self._entries.by_candidate(line.candidate_id)
        if entry is None:
            raise CheckoutRefusedError(
                f'catalogue has no entry for {line.candidate_id}'
            )
        if entry.state is not CatalogueEntryState.PUBLISHED:
            raise CheckoutRefusedError(
                f'{line.candidate_id} is not published ({entry.state.value})'
            )
        if entry.listing is not StorefrontListing.PAID_OK:
            raise CheckoutRefusedError(
                f'{line.candidate_id} listing is {entry.listing.value}, not paid_ok'
            )

    def _require_provider(self, provider_id: str) -> PaymentProvider:
        if provider_id not in self._providers:
            raise CheckoutRefusedError(f'unknown payment provider {provider_id}')
        return self._providers[provider_id]

    @staticmethod
    def _pending_order(cart: Cart, now: datetime) -> Order:
        lines = tuple(
            OrderLine(
                candidate_id=line.candidate_id,
                unit_amount=line.unit_amount,
                quantity=line.quantity,
            )
            for line in cart.lines
        )
        total = sum(
            (line.unit_amount * line.quantity for line in lines),
            Decimal('0'),
        )
        return Order(
            order_id=str(uuid.uuid4()),
            buyer_id=cart.buyer_id,
            state=OrderState.PENDING,
            currency=cart.currency,
            lines=lines,
            total=total,
            provider_id=None,
            provider_reference=None,
            created_at=now,
            paid_at=None,
        )

    async def _mark_failed(self, order: Order) -> Order:
        if order.state is OrderState.PAID:
            return order
        failed = order.model_copy(update={'state': OrderState.FAILED})
        await self._orders.save_order(failed)
        return failed

    @staticmethod
    def _idempotent_or_conflict(
        order: Order, confirmation: PaymentConfirmation
    ) -> Order:
        if order.provider_reference == confirmation.provider_reference:
            return order
        raise CheckoutRefusedError(
            f'order {order.order_id} is already paid under a different reference'
        )

    async def _grant_entitlements(self, order: Order, now: datetime) -> None:
        for line in order.lines:
            await self._entitlements.save_entitlement(
                Entitlement(
                    buyer_id=order.buyer_id,
                    candidate_id=line.candidate_id,
                    order_id=order.order_id,
                    granted_at=now,
                    state=EntitlementState.ACTIVE,
                    revoked_at=None,
                    revocation_reason=None,
                )
            )
