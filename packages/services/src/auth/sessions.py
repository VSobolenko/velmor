from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from packages.services.src.domain.account import Session
from packages.services.src.persistence.contract import SessionRepository


class SessionService:
    """Issue, verify and revoke opaque sessions.

    The credential is ``secrets.token_urlsafe(32)`` and only its SHA-256 is
    stored, so a database read yields no value that authenticates. The hash is
    not salted on purpose: the token is 256 bits of uniform randomness, so there
    is nothing to guess and a slow hash would only delay every request.
    """

    TOKEN_BYTES = 32

    def __init__(self, sessions: SessionRepository, lifetime_seconds: int) -> None:
        self._sessions = sessions
        self._lifetime_seconds = lifetime_seconds

    async def issue(self, user_id: str, now: datetime) -> str:
        token = secrets.token_urlsafe(self.TOKEN_BYTES)
        await self._sessions.save_session(
            Session(
                token_hash=self.hash_token(token),
                user_id=user_id,
                created_at=now,
                expires_at=now + timedelta(seconds=self._lifetime_seconds),
                revoked_at=None,
            )
        )
        return token

    async def authenticate(self, token: str, now: datetime) -> Session | None:
        session = await self._sessions.by_token_hash(self.hash_token(token))
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            return None
        return session

    async def revoke(self, token: str, now: datetime) -> None:
        await self._sessions.revoke_session(self.hash_token(token), now)

    async def revoke_others(self, user_id: str, token: str, now: datetime) -> None:
        await self._sessions.revoke_other_sessions(
            user_id, self.hash_token(token), now
        )

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
