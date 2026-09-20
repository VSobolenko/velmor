from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class CartLine(BaseModel):
    """One good the buyer intends to purchase. Not persisted in this change."""

    model_config = {'frozen': True}

    candidate_id: str
    unit_amount: Decimal
    quantity: int


class Cart(BaseModel):
    """Checkout input held by the storefront until payment is started."""

    model_config = {'frozen': True}

    buyer_id: str
    currency: str
    lines: tuple[CartLine, ...]
