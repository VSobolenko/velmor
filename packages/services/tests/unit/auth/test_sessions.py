from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from packages.services.src.auth.sessions import SessionService
from packages.services.src.persistence.memory import InMemoryStore

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
LIFETIME_SECONDS = 3600


def build_service() -> tuple[SessionService, InMemoryStore]:
    store = InMemoryStore()
    return SessionService(store, LIFETIME_SECONDS), store


class TestSessionLifetime:
    async def test_a_just_issued_token_authenticates(self) -> None:
        service, _store = build_service()

        token = await service.issue('account-1', NOW)

        session = await service.authenticate(token, NOW)
        assert session is not None
        assert session.user_id == 'account-1'

    async def test_only_the_hash_of_the_token_is_stored(self) -> None:
        service, store = build_service()

        token = await service.issue('account-1', NOW)

        stored = await store.by_token_hash(SessionService.hash_token(token))
        assert stored is not None
        assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token != stored.token_hash

    async def test_a_token_that_was_never_issued_grants_nothing(self) -> None:
        service, _store = build_service()

        assert await service.authenticate('never-issued', NOW) is None

    async def test_an_expired_session_grants_nothing(self) -> None:
        service, _store = build_service()
        token = await service.issue('account-1', NOW)

        after_expiry = NOW + timedelta(seconds=LIFETIME_SECONDS + 1)

        assert await service.authenticate(token, after_expiry) is None

    async def test_a_session_at_its_expiry_grants_nothing(self) -> None:
        service, _store = build_service()
        token = await service.issue('account-1', NOW)

        at_expiry = NOW + timedelta(seconds=LIFETIME_SECONDS)

        assert await service.authenticate(token, at_expiry) is None

    async def test_a_revoked_session_grants_nothing(self) -> None:
        service, _store = build_service()
        token = await service.issue('account-1', NOW)

        await service.revoke(token, NOW)

        assert await service.authenticate(token, NOW) is None

    async def test_signing_in_again_issues_a_different_token(self) -> None:
        service, _store = build_service()

        first = await service.issue('account-1', NOW)
        second = await service.issue('account-1', NOW)

        assert first != second
        assert await service.authenticate(first, NOW) is not None
        assert await service.authenticate(second, NOW) is not None

    async def test_revoking_others_leaves_the_acting_session_working(self) -> None:
        service, _store = build_service()
        acting = await service.issue('account-1', NOW)
        other = await service.issue('account-1', NOW)

        await service.revoke_others('account-1', acting, NOW)

        assert await service.authenticate(acting, NOW) is not None
        assert await service.authenticate(other, NOW) is None

    async def test_revoking_others_leaves_another_accounts_sessions_alone(self) -> None:
        service, _store = build_service()
        mine = await service.issue('account-1', NOW)
        theirs = await service.issue('account-2', NOW)

        await service.revoke_others('account-1', mine, NOW)

        assert await service.authenticate(theirs, NOW) is not None
