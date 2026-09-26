from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.services.src.auth.password import PasswordHasher
from packages.services.src.auth.service import AccountService
from packages.services.src.persistence.memory import InMemoryStore

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
PASSWORD = 'a sufficiently long password'
NEW_PASSWORD = 'an equally long new password'
MIN_LENGTH = 10
ATTEMPT_LIMIT = 3
WINDOW_SECONDS = 900
LIFETIME_SECONDS = 3600
EMAIL = 'buyer@example.test'


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant


class Harness:
    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.clock = FixedClock(NOW)
        self.service = AccountService(
            accounts=self.store,
            sessions=self.store,
            clock=self.clock,
            password_min_length=MIN_LENGTH,
            failed_attempt_limit=ATTEMPT_LIMIT,
            failed_attempt_window_seconds=WINDOW_SECONDS,
            session_lifetime_seconds=LIFETIME_SECONDS,
        )


class TestRegistration:
    async def test_a_new_address_creates_an_account_and_signs_in(self) -> None:
        harness = Harness()

        outcome = await harness.service.register('  Buyer@Example.TEST  ', PASSWORD, '  Buyer  ')

        assert outcome.reason is None
        assert outcome.account is not None
        assert outcome.account.email == 'buyer@example.test'
        assert outcome.account.display_name == 'Buyer'
        assert outcome.token is not None
        assert await harness.service.authenticate(outcome.token) == outcome.account

    async def test_a_duplicate_address_in_any_case_is_refused(self) -> None:
        harness = Harness()
        original = await harness.service.register(EMAIL, PASSWORD, 'Buyer')

        outcome = await harness.service.register('  BUYER@EXAMPLE.TEST  ', PASSWORD, 'Impostor')

        assert outcome.reason == AccountService.EMAIL_UNAVAILABLE
        assert outcome.account is None
        stored = await harness.store.by_email(EMAIL)
        assert stored == original.account

    async def test_a_password_below_the_minimum_is_refused(self) -> None:
        harness = Harness()

        outcome = await harness.service.register(EMAIL, 'too-short', 'Buyer')

        assert outcome.reason == AccountService.PASSWORD_TOO_SHORT
        assert await harness.store.by_email(EMAIL) is None

    @pytest.mark.parametrize('email', ['', '   ', '\t'])
    async def test_an_empty_address_is_refused(self, email: str) -> None:
        harness = Harness()

        outcome = await harness.service.register(email, PASSWORD, 'Buyer')

        assert outcome.reason == AccountService.EMAIL_REQUIRED
        assert outcome.account is None

    async def test_the_stored_value_is_not_the_password(self) -> None:
        harness = Harness()

        outcome = await harness.service.register(EMAIL, PASSWORD, 'Buyer')

        account = outcome.account
        assert account is not None
        assert account.password_hash != PASSWORD
        assert PASSWORD not in account.password_hash
        assert PASSWORD not in account.password_salt

    async def test_two_accounts_with_one_password_store_different_values(self) -> None:
        harness = Harness()

        first = await harness.service.register('one@example.test', PASSWORD, 'One')
        second = await harness.service.register('two@example.test', PASSWORD, 'Two')

        assert first.account is not None
        assert second.account is not None
        assert first.account.password_hash != second.account.password_hash
        assert first.account.password_salt != second.account.password_salt
        hasher = PasswordHasher()
        assert hasher.matches(
            PASSWORD, first.account.password_hash, first.account.password_salt
        )
        assert hasher.matches(
            PASSWORD, second.account.password_hash, second.account.password_salt
        )


class TestSignInAndOut:
    async def test_correct_credentials_sign_the_buyer_in(self) -> None:
        harness = Harness()
        await harness.service.register(EMAIL, PASSWORD, 'Buyer')

        outcome = await harness.service.sign_in(EMAIL, PASSWORD)

        assert outcome.reason is None
        assert outcome.token is not None
        assert await harness.service.authenticate(outcome.token) is not None

    async def test_a_wrong_password_and_an_unknown_address_are_refused_identically(
        self,
    ) -> None:
        harness = Harness()
        await harness.service.register(EMAIL, PASSWORD, 'Buyer')

        wrong = await harness.service.sign_in(EMAIL, 'the wrong password')
        unknown = await harness.service.sign_in('nobody@example.test', 'the wrong password')

        assert wrong.reason == AccountService.INVALID_CREDENTIALS
        assert unknown.reason == AccountService.INVALID_CREDENTIALS
        assert wrong.account is None
        assert unknown.account is None

    async def test_signing_in_again_issues_a_different_credential(self) -> None:
        harness = Harness()
        await harness.service.register(EMAIL, PASSWORD, 'Buyer')

        first = await harness.service.sign_in(EMAIL, PASSWORD)
        second = await harness.service.sign_in(EMAIL, PASSWORD)

        assert first.token != second.token

    async def test_signing_out_revokes_the_session(self) -> None:
        harness = Harness()
        registered = await harness.service.register(EMAIL, PASSWORD, 'Buyer')

        await harness.service.sign_out(registered.token)

        assert await harness.service.authenticate(registered.token) is None


class TestRateLimit:
    async def test_repeated_failures_are_throttled(self) -> None:
        harness = Harness()
        await harness.service.register(EMAIL, PASSWORD, 'Buyer')
        for _attempt in range(ATTEMPT_LIMIT):
            refused = await harness.service.sign_in(EMAIL, 'the wrong password')
            assert refused.reason == AccountService.INVALID_CREDENTIALS

        throttled = await harness.service.sign_in(EMAIL, PASSWORD)

        assert throttled.reason == AccountService.RATE_LIMITED
        assert throttled.token is None

    async def test_a_correct_password_after_the_window_signs_in(self) -> None:
        harness = Harness()
        await harness.service.register(EMAIL, PASSWORD, 'Buyer')
        for _attempt in range(ATTEMPT_LIMIT):
            await harness.service.sign_in(EMAIL, 'the wrong password')
        harness.clock.instant = NOW + timedelta(seconds=WINDOW_SECONDS + 1)

        outcome = await harness.service.sign_in(EMAIL, PASSWORD)

        assert outcome.reason is None
        assert outcome.token is not None
        assert await harness.service.authenticate(outcome.token) is not None


class TestChangePassword:
    async def test_the_new_password_signs_in_and_the_old_one_stops(self) -> None:
        harness = Harness()
        registered = await harness.service.register(EMAIL, PASSWORD, 'Buyer')
        account_id = registered.account.account_id

        outcome = await harness.service.change_password(
            account_id, registered.token, PASSWORD, NEW_PASSWORD
        )

        assert outcome.reason is None
        old = await harness.service.sign_in(EMAIL, PASSWORD)
        new = await harness.service.sign_in(EMAIL, NEW_PASSWORD)
        assert old.reason == AccountService.INVALID_CREDENTIALS
        assert new.reason is None

    async def test_a_wrong_current_password_is_refused_and_changes_nothing(self) -> None:
        harness = Harness()
        registered = await harness.service.register(EMAIL, PASSWORD, 'Buyer')
        account_id = registered.account.account_id
        before = await harness.store.by_account_id(account_id)

        outcome = await harness.service.change_password(
            account_id, registered.token, 'the wrong current password', NEW_PASSWORD
        )

        assert outcome.reason == AccountService.CURRENT_PASSWORD_INCORRECT
        assert await harness.store.by_account_id(account_id) == before

    async def test_a_short_new_password_is_refused_and_changes_nothing(self) -> None:
        harness = Harness()
        registered = await harness.service.register(EMAIL, PASSWORD, 'Buyer')
        account_id = registered.account.account_id
        before = await harness.store.by_account_id(account_id)

        outcome = await harness.service.change_password(
            account_id, registered.token, PASSWORD, 'too-short'
        )

        assert outcome.reason == AccountService.PASSWORD_TOO_SHORT
        assert await harness.store.by_account_id(account_id) == before

    async def test_changing_the_password_closes_other_sessions(self) -> None:
        harness = Harness()
        acting = await harness.service.register(EMAIL, PASSWORD, 'Buyer')
        other = await harness.service.sign_in(EMAIL, PASSWORD)

        outcome = await harness.service.change_password(
            acting.account.account_id, acting.token, PASSWORD, NEW_PASSWORD
        )

        assert outcome.reason is None
        assert await harness.service.authenticate(acting.token) is not None
        assert await harness.service.authenticate(other.token) is None
