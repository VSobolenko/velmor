from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.services.src.domain.account import Account, Session
from packages.services.src.persistence.contract import (
    AccountRepository,
    SessionRepository,
)
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.persistence.postgres import PostgresStore

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
UNCONNECTED_DSN = 'postgresql+asyncpg://localhost/velmor'


def build_account(
    account_id: str = 'account-1',
    email: str = 'buyer@example.test',
    *,
    failed_attempts: int = 0,
    last_failed_at: datetime | None = None,
) -> Account:
    return Account(
        account_id=account_id,
        email=email,
        display_name='Buyer',
        password_hash='not-the-password',
        password_salt='per-user-salt',
        failed_attempts=failed_attempts,
        last_failed_at=last_failed_at,
    )


def build_session(
    token_hash: str = 'token-hash-1',
    user_id: str = 'account-1',
) -> Session:
    return Session(
        token_hash=token_hash,
        user_id=user_id,
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        revoked_at=None,
    )


class TestAccountRepository:
    async def test_an_account_round_trips_by_email_and_id(self) -> None:
        store = InMemoryStore()
        account = build_account()

        written = await store.create_account(account)

        assert written is True
        assert await store.by_email('buyer@example.test') == account
        assert await store.by_account_id('account-1') == account

    async def test_an_address_already_in_use_is_not_written(self) -> None:
        store = InMemoryStore()
        original = build_account()
        await store.create_account(original)

        written = await store.create_account(build_account('account-2'))

        assert written is False
        assert await store.by_account_id('account-2') is None
        assert await store.by_email('buyer@example.test') == original

    async def test_an_unknown_address_or_id_has_no_account(self) -> None:
        store = InMemoryStore()

        assert await store.by_email('nobody@example.test') is None
        assert await store.by_account_id('account-missing') is None

    async def test_save_account_replaces_the_stored_row(self) -> None:
        store = InMemoryStore()
        await store.create_account(build_account())
        changed = build_account().model_copy(update={'display_name': 'Renamed'})

        await store.save_account(changed)

        assert await store.by_account_id('account-1') == changed


class TestFailedSignInCounter:
    async def test_failures_accumulate_within_the_window(self) -> None:
        store = InMemoryStore()
        await store.create_account(build_account())

        await store.record_failed_sign_in('account-1', NOW, 900)
        await store.record_failed_sign_in('account-1', NOW + timedelta(seconds=1), 900)

        stored = await store.by_account_id('account-1')
        assert stored is not None
        assert stored.failed_attempts == 2

    async def test_the_counter_starts_over_after_the_window(self) -> None:
        store = InMemoryStore()
        await store.create_account(build_account())
        await store.record_failed_sign_in('account-1', NOW, 900)

        await store.record_failed_sign_in('account-1', NOW + timedelta(seconds=901), 900)

        stored = await store.by_account_id('account-1')
        assert stored is not None
        assert stored.failed_attempts == 1

    async def test_a_successful_sign_in_clears_the_counter(self) -> None:
        store = InMemoryStore()
        await store.create_account(build_account(failed_attempts=3, last_failed_at=NOW))

        await store.clear_failed_sign_ins('account-1')

        stored = await store.by_account_id('account-1')
        assert stored is not None
        assert stored.failed_attempts == 0
        assert stored.last_failed_at is None


class TestSessionRepository:
    async def test_a_session_round_trips_by_token_hash(self) -> None:
        store = InMemoryStore()
        session = build_session()

        await store.save_session(session)

        assert await store.by_token_hash('token-hash-1') == session

    async def test_an_unknown_token_hash_has_no_session(self) -> None:
        store = InMemoryStore()

        assert await store.by_token_hash('token-hash-missing') is None

    async def test_revoking_sets_the_timestamp(self) -> None:
        store = InMemoryStore()
        await store.save_session(build_session())

        await store.revoke_session('token-hash-1', NOW)

        stored = await store.by_token_hash('token-hash-1')
        assert stored is not None
        assert stored.revoked_at == NOW

    async def test_revoking_an_unknown_session_is_a_noop(self) -> None:
        store = InMemoryStore()

        await store.revoke_session('token-hash-missing', NOW)

        assert await store.by_token_hash('token-hash-missing') is None

    async def test_revoking_others_leaves_the_named_session_and_other_accounts(
        self,
    ) -> None:
        store = InMemoryStore()
        acting = build_session('acting-hash', 'account-1')
        other = build_session('other-hash', 'account-1')
        elsewhere = build_session('elsewhere-hash', 'account-2')
        for session in (acting, other, elsewhere):
            await store.save_session(session)

        await store.revoke_other_sessions('account-1', 'acting-hash', NOW)

        stored_acting = await store.by_token_hash('acting-hash')
        stored_other = await store.by_token_hash('other-hash')
        stored_elsewhere = await store.by_token_hash('elsewhere-hash')
        assert stored_acting is not None
        assert stored_acting.revoked_at is None
        assert stored_other is not None
        assert stored_other.revoked_at == NOW
        assert stored_elsewhere is not None
        assert stored_elsewhere.revoked_at is None


class TestAuthRepositoryConformance:
    def test_the_in_memory_store_satisfies_both_auth_protocols(self) -> None:
        store = InMemoryStore()

        assert isinstance(store, AccountRepository)
        assert isinstance(store, SessionRepository)

    async def test_the_postgres_store_satisfies_both_auth_protocols(self) -> None:
        engine = create_async_engine(UNCONNECTED_DSN)
        store = PostgresStore(engine, async_sessionmaker(engine, expire_on_commit=False))

        assert isinstance(store, AccountRepository)
        assert isinstance(store, SessionRepository)

        await engine.dispose()

    def test_a_class_missing_a_method_does_not_satisfy_the_protocol(self) -> None:
        class IncompleteAccounts:
            async def create_account(self, account: Account) -> bool: ...

            async def save_account(self, account: Account) -> None: ...

            async def by_email(self, email: str) -> Account | None: ...

            async def by_account_id(self, account_id: str) -> Account | None: ...

            async def record_failed_sign_in(
                self, account_id: str, now: datetime, window_seconds: int
            ) -> None: ...

        class IncompleteSessions:
            async def save_session(self, session: Session) -> None: ...

            async def by_token_hash(self, token_hash: str) -> Session | None: ...

            async def revoke_session(self, token_hash: str, now: datetime) -> None: ...

        assert not isinstance(IncompleteAccounts(), AccountRepository)
        assert not isinstance(IncompleteSessions(), SessionRepository)
