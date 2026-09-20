from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class OrderState(StrEnum):
    """Lifecycle of a checkout order from payment start through settlement."""

    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class OrderLine(BaseModel):
    """One good on an order. Digital goods use quantity 1 in this change."""

    model_config = {'frozen': True}

    candidate_id: str
    unit_amount: Decimal
    quantity: int


class Order(BaseModel):
    """A buyer's payment attempt for one cart, independent of the provider.

    ``provider_id`` and ``provider_reference`` are set when payment is started.
    ``total`` must equal the sum of ``unit_amount * quantity`` across ``lines``.
    """

    model_config = {'frozen': True}

    order_id: str
    buyer_id: str
    state: OrderState
    currency: str
    lines: tuple[OrderLine, ...]
    total: Decimal
    provider_id: str | None = None
    provider_reference: str | None = None
    created_at: datetime
    paid_at: datetime | None = None
