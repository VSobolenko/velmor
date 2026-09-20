from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from packages.services.src.commerce.errors import GrantRefusedError
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.entitlement import DeliveryGrant

SECRET = SecretStr('unit-test-delivery-grant-secret')
LIFETIME = 900
BUYER = 'buyer-1'
OTHER_BUYER = 'buyer-2'
CANDIDATE = 'openverse:1'
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


class TestDeliveryGrantService:
    def test_issue_and_verify_round_trip_for_same_buyer(self) -> None:
        service = DeliveryGrantService(secret=SECRET, lifetime_seconds=LIFETIME)

        token, grant = service.issue(BUYER, CANDIDATE, NOW)
        verified = service.verify(token, BUYER, NOW)

        assert isinstance(grant, DeliveryGrant)
        assert grant.buyer_id == BUYER
        assert grant.candidate_id == CANDIDATE
        assert grant.issued_at == NOW
        assert grant.expires_at == NOW + timedelta(seconds=LIFETIME)
        assert verified == grant
        assert token  # non-empty URL-safe token

    def test_expired_grant_is_refused(self) -> None:
        service = DeliveryGrantService(secret=SECRET, lifetime_seconds=LIFETIME)
        token, grant = service.issue(BUYER, CANDIDATE, NOW)
        after_expiry = grant.expires_at

        with pytest.raises(GrantRefusedError, match='expired') as caught:
            service.verify(token, BUYER, after_expiry)

        assert SECRET.get_secret_value() not in str(caught.value)
        assert token not in str(caught.value)

    def test_wrong_buyer_is_refused(self) -> None:
        service = DeliveryGrantService(secret=SECRET, lifetime_seconds=LIFETIME)
        token, _grant = service.issue(BUYER, CANDIDATE, NOW)

        with pytest.raises(GrantRefusedError) as caught:
            service.verify(token, OTHER_BUYER, NOW)

        assert 'buyer' in str(caught.value).lower() or 'different' in str(caught.value).lower()
        assert SECRET.get_secret_value() not in str(caught.value)

    def test_tampered_token_is_refused(self) -> None:
        service = DeliveryGrantService(secret=SECRET, lifetime_seconds=LIFETIME)
        token, _grant = service.issue(BUYER, CANDIDATE, NOW)
        # Flip one character in the signature half so the HMAC no longer matches.
        body, signature = token.rsplit('.', 1)
        flipped = 'A' if signature[0] != 'A' else 'B'
        tampered = f'{body}.{flipped}{signature[1:]}'

        with pytest.raises(GrantRefusedError) as caught:
            service.verify(tampered, BUYER, NOW)

        assert SECRET.get_secret_value() not in str(caught.value)
        assert tampered not in str(caught.value)
