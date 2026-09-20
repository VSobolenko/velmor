from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class EntitlementState(StrEnum):
    """Whether a buyer may still download the good an order paid for.

    Revocation is a state rather than a deleted row: a refused download has to
    report why, and the order and the record behind it stay auditable.
    """

    ACTIVE = 'active'
    REVOKED = 'revoked'


class Entitlement(BaseModel):
    """A buyer's right to download one good, created by a paid order.

    An entitlement never exists without the order that granted it. Validity is
    ``granted_at`` plus ``state``; no expiry is modelled, because no requirement
    asks a purchase to lapse. ``revoked_at`` and ``revocation_reason`` are set
    only by revocation, which is what lets a refused download explain itself.
    """

    model_config = {'frozen': True}

    buyer_id: str
    candidate_id: str
    order_id: str
    granted_at: datetime
    state: EntitlementState
    revoked_at: datetime | None = None
    revocation_reason: str | None = None


class DeliveryGrant(BaseModel):
    """A short-lived authorisation to fetch one purchased good, bound to a buyer.

    The grant carries no token and no signature: how a link is encoded and
    verified belongs to the delivery endpoint. What it fixes is that the
    authorisation expires and belongs to exactly one buyer, so a link used after
    ``expires_at``, or by anyone other than ``buyer_id``, is refused.
    """

    model_config = {'frozen': True}

    grant_id: str
    buyer_id: str
    candidate_id: str
    issued_at: datetime
    expires_at: datetime
