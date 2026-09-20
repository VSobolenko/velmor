from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from packages.services.src.domain.order import Order


class PaymentStart(BaseModel):
    """What a provider returns when a payment session is created."""

    model_config = {'frozen': True}

    redirect_url: str
    provider_reference: str


class PaymentConfirmation(BaseModel):
    """A provider's report that a payment succeeded or failed.

    Authentication of the notification belongs to the concrete provider
    (tasks 5.2 / 5.3). This model is the already-authenticated payload passed
    into ``CheckoutService.confirm``.
    """

    model_config = {'frozen': True}

    provider_reference: str
    order_id: str
    amount: Decimal
    currency: str
    succeeded: bool


class PaymentProvider(Protocol):
    """Interchangeable payment backend. Stripe and bePaid implement this later."""

    @property
    def provider_id(self) -> str: ...

    async def start_payment(self, order: Order, return_url: str) -> PaymentStart: ...
