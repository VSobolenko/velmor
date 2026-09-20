from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from packages.services.src.domain.entitlement import (
    DeliveryGrant,
    Entitlement,
    EntitlementState,
)

GRANTED_AT = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
ISSUED_AT = datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc)


def build_entitlement(
    buyer_id: str = 'buyer-1',
    candidate_id: str = 'openverse:1',
    order_id: str = 'order-1',
    granted_at: datetime = GRANTED_AT,
    state: EntitlementState = EntitlementState.ACTIVE,
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


def build_grant(
    grant_id: str = 'grant-1',
    buyer_id: str = 'buyer-1',
    candidate_id: str = 'openverse:1',
    issued_at: datetime = ISSUED_AT,
    expires_at: datetime = ISSUED_AT + timedelta(minutes=15),
) -> DeliveryGrant:
    return DeliveryGrant(
        grant_id=grant_id,
        buyer_id=buyer_id,
        candidate_id=candidate_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )


class TestEntitlementState:
    def test_the_state_values_are_the_strings_the_system_persists(self) -> None:
        assert EntitlementState.ACTIVE == 'active'
        assert EntitlementState.REVOKED == 'revoked'

    def test_there_are_exactly_two_states(self) -> None:
        assert set(EntitlementState) == {
            EntitlementState.ACTIVE,
            EntitlementState.REVOKED,
        }


class TestEntitlement:
    def test_an_entitlement_records_the_paid_order_that_granted_it(self) -> None:
        entitlement = build_entitlement()

        assert entitlement.buyer_id == 'buyer-1'
        assert entitlement.candidate_id == 'openverse:1'
        assert entitlement.order_id == 'order-1'
        assert entitlement.granted_at == GRANTED_AT
        assert entitlement.state is EntitlementState.ACTIVE

    def test_the_revocation_fields_default_to_none(self) -> None:
        entitlement = build_entitlement()

        assert entitlement.revoked_at is None
        assert entitlement.revocation_reason is None

    def test_a_revoked_entitlement_reports_when_and_why(self) -> None:
        entitlement = build_entitlement(
            state=EntitlementState.REVOKED,
            revoked_at=GRANTED_AT + timedelta(days=1),
            revocation_reason='order refunded',
        )

        assert entitlement.state is EntitlementState.REVOKED
        assert entitlement.revoked_at == GRANTED_AT + timedelta(days=1)
        assert entitlement.revocation_reason == 'order refunded'

    def test_a_missing_order_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Entitlement(
                buyer_id='buyer-1',
                candidate_id='openverse:1',
                granted_at=GRANTED_AT,
                state=EntitlementState.ACTIVE,
            )

    def test_an_entitlement_is_frozen(self) -> None:
        entitlement = build_entitlement()

        with pytest.raises(ValidationError):
            entitlement.state = EntitlementState.REVOKED


class TestDeliveryGrant:
    def test_a_grant_is_short_lived_and_bound_to_its_buyer(self) -> None:
        grant = build_grant()

        assert grant.grant_id == 'grant-1'
        assert grant.buyer_id == 'buyer-1'
        assert grant.candidate_id == 'openverse:1'
        assert grant.issued_at == ISSUED_AT
        assert grant.expires_at > grant.issued_at

    def test_a_missing_buyer_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DeliveryGrant(
                grant_id='grant-1',
                candidate_id='openverse:1',
                issued_at=ISSUED_AT,
                expires_at=ISSUED_AT + timedelta(minutes=15),
            )

    def test_a_grant_is_frozen(self) -> None:
        grant = build_grant()

        with pytest.raises(ValidationError):
            grant.expires_at = ISSUED_AT
