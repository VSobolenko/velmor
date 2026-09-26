from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime

from packages.services.src.auth.password import PasswordHasher
from packages.services.src.auth.sessions import SessionService
from packages.services.src.domain.account import Account, AccountOutcome
from packages.services.src.persistence.contract import AccountRepository, SessionRepository


class AccountService:
    """Registration, sign-in, sign-out, profile and password change.

    A refusal is a stable code, never a sentence: the buyer-facing copy is
    written by the surface, in the reader's language, from the code. The minimum
    password length stays a setting and is reported beside the code, not baked
    into it. ``INVALID_CREDENTIALS`` is returned for both a wrong password and an
    unknown address, so a refusal cannot be used to discover which accounts
    exist.
    """

    INVALID_CREDENTIALS = 'invalid_credentials'
    EMAIL_UNAVAILABLE = 'email_unavailable'
    EMAIL_REQUIRED = 'email_required'
    PASSWORD_TOO_SHORT = 'password_too_short'
    CURRENT_PASSWORD_INCORRECT = 'current_password_incorrect'
    RATE_LIMITED = 'rate_limited'

    def __init__(
        self,
        accounts: AccountRepository,
        sessions: SessionRepository,
        clock: Callable[[], datetime],
        password_min_length: int,
        failed_attempt_limit: int,
        failed_attempt_window_seconds: int,
        session_lifetime_seconds: int,
    ) -> None:
        self._accounts = accounts
        self._clock = clock
        self._password_min_length = password_min_length
        self._failed_attempt_limit = failed_attempt_limit
        self._failed_attempt_window_seconds = failed_attempt_window_seconds
        self._hasher = PasswordHasher()
        self._session_service = SessionService(sessions, session_lifetime_seconds)

    async def register(
        self, email: str, password: str, display_name: str
    ) -> AccountOutcome:
        normalized = email.strip().lower()
        if normalized == '':
            return self._refused(self.EMAIL_REQUIRED)
        if len(password) < self._password_min_length:
            return self._refused(self.PASSWORD_TOO_SHORT)
        password_hash, password_salt = self._hasher.hash(password)
        account = Account(
            account_id=secrets.token_urlsafe(16),
            email=normalized,
            display_name=display_name.strip(),
            password_hash=password_hash,
            password_salt=password_salt,
            failed_attempts=0,
            last_failed_at=None,
        )
        if not await self._accounts.create_account(account):
            return self._refused(self.EMAIL_UNAVAILABLE)
        token = await self._session_service.issue(account.account_id, self._clock())
        return AccountOutcome(account=account, token=token, reason=None)

    async def sign_in(self, email: str, password: str) -> AccountOutcome:
        account = await self._accounts.by_email(email.strip().lower())
        if account is None:
            return self._refused(self.INVALID_CREDENTIALS)
        now = self._clock()
        if self._is_rate_limited(account, now):
            return self._refused(self.RATE_LIMITED)
        if not self._hasher.matches(
            password, account.password_hash, account.password_salt
        ):
            await self._accounts.record_failed_sign_in(
                account.account_id, now, self._failed_attempt_window_seconds
            )
            return self._refused(self.INVALID_CREDENTIALS)
        await self._accounts.clear_failed_sign_ins(account.account_id)
        token = await self._session_service.issue(account.account_id, now)
        return AccountOutcome(account=account, token=token, reason=None)

    async def authenticate(self, token: str) -> Account | None:
        session = await self._session_service.authenticate(token, self._clock())
        if session is None:
            return None
        return await self._accounts.by_account_id(session.user_id)

    async def sign_out(self, token: str) -> None:
        await self._session_service.revoke(token, self._clock())

    async def change_password(
        self, account_id: str, token: str, current_password: str, new_password: str
    ) -> AccountOutcome:
        account = await self._accounts.by_account_id(account_id)
        if account is None or not self._hasher.matches(
            current_password, account.password_hash, account.password_salt
        ):
            return self._refused(self.CURRENT_PASSWORD_INCORRECT)
        if len(new_password) < self._password_min_length:
            return self._refused(self.PASSWORD_TOO_SHORT)
        password_hash, password_salt = self._hasher.hash(new_password)
        updated = account.model_copy(
            update={'password_hash': password_hash, 'password_salt': password_salt}
        )
        await self._accounts.save_account(updated)
        await self._session_service.revoke_others(account_id, token, self._clock())
        return AccountOutcome(account=updated, token=None, reason=None)

    def _is_rate_limited(self, account: Account, now: datetime) -> bool:
        if account.last_failed_at is None:
            return False
        elapsed = (now - account.last_failed_at).total_seconds()
        if elapsed > self._failed_attempt_window_seconds:
            return False
        return account.failed_attempts >= self._failed_attempt_limit

    @staticmethod
    def _refused(code: str) -> AccountOutcome:
        return AccountOutcome(account=None, token=None, reason=code)
