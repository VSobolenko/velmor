from __future__ import annotations

from packages.services.src.domain.gate import GateDecision
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate, build_record


class TestStorefrontCatalog:
    """The storefront reads the gate's own verdict, so a refusal is unreachable."""

    async def test_only_publishable_goods_are_listed(self) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            (
                build_candidate(candidate_id='openverse:allowed'),
                build_candidate(candidate_id='openverse:refused'),
            )
        )
        await store.save(
            GateDecision(
                candidate_id='openverse:allowed',
                publishable=True,
                reasons=(),
                record=build_record().model_copy(update={'candidate_id': 'openverse:allowed'}),
            )
        )
        await store.save(
            GateDecision(
                candidate_id='openverse:refused',
                publishable=False,
                reasons=('declared licence does not permit resale',),
                record=build_record().model_copy(update={'candidate_id': 'openverse:refused'}),
            )
        )

        published = await store.published(10)

        assert [candidate.id for candidate, _ in published] == ['openverse:allowed']

    async def test_a_candidate_with_no_verdict_is_not_listed(self) -> None:
        store = InMemoryStore()
        await store.upsert_many((build_candidate(candidate_id='openverse:pending'),))

        assert await store.published(10) == ()

    async def test_the_record_travels_with_the_candidate(self) -> None:
        store = InMemoryStore()
        await store.upsert_many((build_candidate(candidate_id='openverse:1'),))
        record = build_record(license_id='CC0-1.0')
        await store.save(
            GateDecision(
                candidate_id='openverse:1', publishable=True, reasons=(), record=record
            )
        )

        published = await store.published(10)

        assert published == ((build_candidate(candidate_id='openverse:1'), record),)

    async def test_the_limit_bounds_the_listing(self) -> None:
        store = InMemoryStore()
        candidates = tuple(
            build_candidate(candidate_id=f'openverse:{index}') for index in range(4)
        )
        await store.upsert_many(candidates)
        for candidate in candidates:
            await store.save(
                GateDecision(
                    candidate_id=candidate.id,
                    publishable=True,
                    reasons=(),
                    record=build_record().model_copy(update={'candidate_id': candidate.id}),
                )
            )

        assert len(await store.published(2)) == 2

    async def test_the_count_is_not_the_capped_page_size(self) -> None:
        store = InMemoryStore()
        candidates = tuple(
            build_candidate(candidate_id=f'openverse:{index}') for index in range(4)
        )
        await store.upsert_many(candidates)
        for candidate in candidates:
            await store.save(
                GateDecision(
                    candidate_id=candidate.id,
                    publishable=True,
                    reasons=(),
                    record=build_record().model_copy(update={'candidate_id': candidate.id}),
                )
            )

        assert await store.published_count() == 4
        assert len(await store.published(2)) == 2

    async def test_the_count_ignores_refusals_and_candidates_with_no_verdict(self) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            (
                build_candidate(candidate_id='openverse:allowed'),
                build_candidate(candidate_id='openverse:refused'),
                build_candidate(candidate_id='openverse:pending'),
            )
        )
        await store.save(
            GateDecision(
                candidate_id='openverse:allowed',
                publishable=True,
                reasons=(),
                record=build_record().model_copy(update={'candidate_id': 'openverse:allowed'}),
            )
        )
        await store.save(
            GateDecision(
                candidate_id='openverse:refused',
                publishable=False,
                reasons=('declared licence does not permit resale',),
                record=build_record().model_copy(update={'candidate_id': 'openverse:refused'}),
            )
        )

        assert await store.published_count() == 1
