from __future__ import annotations

from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate


class TestCandidateByCandidateId:
    async def test_returns_stored_candidate(self) -> None:
        store = InMemoryStore()
        candidate = build_candidate(candidate_id='openverse:42', title='Looked up')
        await store.upsert_many((candidate,))

        found = await store.by_candidate_id('openverse:42')

        assert found is not None
        assert found.id == 'openverse:42'
        assert found.title == 'Looked up'

    async def test_missing_candidate_returns_none(self) -> None:
        store = InMemoryStore()

        assert await store.by_candidate_id('missing') is None
