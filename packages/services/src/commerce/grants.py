from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from packages.services.src.commerce.errors import GrantRefusedError
from packages.services.src.domain.entitlement import DeliveryGrant


class DeliveryGrantService:
    """Issue and verify short-lived HMAC delivery grants bound to a buyer."""

    _TOKEN_PARTS = 2

    def __init__(self, secret: SecretStr, lifetime_seconds: int) -> None:
        self._secret = secret
        self._lifetime_seconds = lifetime_seconds

    def issue(
        self, buyer_id: str, candidate_id: str, now: datetime
    ) -> tuple[str, DeliveryGrant]:
        grant = DeliveryGrant(
            grant_id=secrets.token_urlsafe(16),
            buyer_id=buyer_id,
            candidate_id=candidate_id,
            issued_at=now,
            expires_at=now + timedelta(seconds=self._lifetime_seconds),
        )
        return self._encode(grant), grant

    def verify(self, token: str, buyer_id: str, now: datetime) -> DeliveryGrant:
        grant = self._decode(token)
        if grant.buyer_id != buyer_id:
            raise GrantRefusedError('grant belongs to a different buyer')
        if now >= grant.expires_at:
            raise GrantRefusedError('grant has expired')
        return grant

    def _encode(self, grant: DeliveryGrant) -> str:
        payload = self._canonical(grant)
        signature = self._sign(payload)
        return f'{self._b64encode(payload)}.{self._b64encode(signature)}'

    def _decode(self, token: str) -> DeliveryGrant:
        parts = token.split('.')
        if len(parts) != self._TOKEN_PARTS:
            raise GrantRefusedError('grant is invalid')
        payload = self._b64decode(parts[0])
        signature = self._b64decode(parts[1])
        expected = self._sign(payload)
        if not hmac.compare_digest(signature, expected):
            raise GrantRefusedError('grant is invalid')
        return self._grant_from_payload(payload)

    def _canonical(self, grant: DeliveryGrant) -> bytes:
        return json.dumps(
            {
                'buyer_id': grant.buyer_id,
                'candidate_id': grant.candidate_id,
                'expires_at': self._format_instant(grant.expires_at),
                'grant_id': grant.grant_id,
                'issued_at': self._format_instant(grant.issued_at),
            },
            separators=(',', ':'),
            sort_keys=True,
        ).encode('utf-8')

    def _grant_from_payload(self, payload: bytes) -> DeliveryGrant:
        data = json.loads(payload.decode('utf-8'))
        return DeliveryGrant(
            grant_id=data['grant_id'],
            buyer_id=data['buyer_id'],
            candidate_id=data['candidate_id'],
            issued_at=self._parse_instant(data['issued_at']),
            expires_at=self._parse_instant(data['expires_at']),
        )

    def _sign(self, payload: bytes) -> bytes:
        return hmac.new(
            self._secret.get_secret_value().encode('utf-8'),
            payload,
            hashlib.sha256,
        ).digest()

    @staticmethod
    def _format_instant(instant: datetime) -> str:
        return instant.astimezone(UTC).isoformat().replace('+00:00', 'Z')

    @staticmethod
    def _parse_instant(raw: str) -> datetime:
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))

    @staticmethod
    def _b64encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')

    @staticmethod
    def _b64decode(data: str) -> bytes:
        padding = '=' * (-len(data) % 4)
        # base64.urlsafe_b64decode raises binascii.Error when the input is not
        # valid base64 (incorrect padding or non-alphabet). See Python stdlib
        # docs for binascii.Error / base64. Map to GrantRefusedError so a bad
        # token is a refusal, not a 500.
        try:
            return base64.urlsafe_b64decode(data + padding)
        except binascii.Error as error:
            raise GrantRefusedError('grant is invalid') from error
