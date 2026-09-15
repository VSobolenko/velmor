from __future__ import annotations

from packages.scout.src.ingest import ScoutJob
from packages.scout.src.runner import ScoutRunner
from packages.services.src.connectors.contract import SourceConnector
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.query import SearchQuery
from packages.services.src.domain.source import SourceSpec
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.sources.source_registry import SourceRegistry
from packages.services.tests.conftest import (
    FailingConnector,
    FakeConnector,
    FakeConnectorFactory,
    FakeCredentials,
    build_candidate,
    build_spec,
)

OPENVERSE = build_spec('openverse')
WIKIMEDIA = build_spec('wikimedia-commons')
GITHUB = build_spec('github', enabled=False)
QUERY = SearchQuery(text='vintage poster', limit=5)
PAGE_LIMIT = 5
INTERVAL_SECONDS = 60


class UnreadablePayloadConnector(FakeConnector):
    """A source that answers, but with a payload Velmor cannot turn into candidates."""

    async def discover(self, query: SearchQuery) -> tuple[Candidate, ...]:
        raise ValueError("missing key 'results' in the response body")


def build_over(
    store: InMemoryStore,
    specs: tuple[SourceSpec, ...],
    connectors: dict[str, SourceConnector],
) -> ScoutJob:
    return ScoutJob(
        registry=SourceRegistry(specs, FakeCredentials()),
        factory=FakeConnectorFactory(connectors),
        repository=store,
    )


def build_job(
    specs: tuple[SourceSpec, ...], connectors: dict[str, SourceConnector]
) -> tuple[ScoutJob, InMemoryStore]:
    store = InMemoryStore()
    return build_over(store, specs, connectors), store


def build_connectors() -> dict[str, SourceConnector]:
    return {
        OPENVERSE.id: FakeConnector(OPENVERSE, ()),
        WIKIMEDIA.id: FakeConnector(WIKIMEDIA, ()),
        GITHUB.id: FakeConnector(GITHUB, ()),
    }


class TestDiscoveryPass:
    async def test_every_enabled_source_is_queried_for_the_term(self) -> None:
        connectors = build_connectors()
        job, _ = build_job((OPENVERSE, WIKIMEDIA, GITHUB), connectors)

        run = await job.run(QUERY, run_id='run-1')

        assert connectors[OPENVERSE.id].queries == [QUERY]
        assert connectors[WIKIMEDIA.id].queries == [QUERY]
        assert run.sources_queried == (OPENVERSE.id, WIKIMEDIA.id)

    async def test_a_disabled_source_is_neither_queried_nor_reported(self) -> None:
        connectors = build_connectors()
        job, _ = build_job((OPENVERSE, WIKIMEDIA, GITHUB), connectors)

        run = await job.run(QUERY, run_id='run-1')

        assert connectors[GITHUB.id].queries == []
        assert GITHUB.id not in run.sources_queried

    async def test_every_query_term_is_run_against_every_source(self) -> None:
        connectors = build_connectors()
        job, _ = build_job((OPENVERSE, WIKIMEDIA), connectors)
        runner = ScoutRunner(
            job,
            queries=('poster', 'logo'),
            page_limit=PAGE_LIMIT,
            interval_seconds=INTERVAL_SECONDS,
        )

        runs = await runner.run_once()

        assert len(runs) == 2
        assert [query.text for query in connectors[OPENVERSE.id].queries] == ['poster', 'logo']
        assert [run.query for run in runs] == ['poster', 'logo']

    async def test_each_query_carries_the_configured_page_limit(self) -> None:
        connectors = build_connectors()
        job, _ = build_job((OPENVERSE,), connectors)
        runner = ScoutRunner(
            job,
            queries=('poster',),
            page_limit=PAGE_LIMIT,
            interval_seconds=INTERVAL_SECONDS,
        )

        await runner.run_once()

        assert connectors[OPENVERSE.id].queries[0].limit == PAGE_LIMIT

    async def test_the_same_candidate_in_two_passes_is_stored_once(self) -> None:
        connectors = build_connectors()
        connectors[OPENVERSE.id] = FakeConnector(
            OPENVERSE, (build_candidate(candidate_id='openverse:1', license_id='CC0-1.0'),)
        )
        job, store = build_job((OPENVERSE,), connectors)

        first = await job.run(QUERY, run_id='run-1')
        second = await job.run(QUERY, run_id='run-2')

        assert first.persisted == 1
        assert second.discovered == 1
        assert second.persisted == 0
        assert store.stored_ids() == ('openverse:1',)

    async def test_a_rewritten_listing_does_not_replace_the_stored_candidate(self) -> None:
        store = InMemoryStore()
        first = build_over(
            store,
            (OPENVERSE,),
            {
                OPENVERSE.id: FakeConnector(
                    OPENVERSE,
                    (build_candidate(candidate_id='openverse:1', title='Windows license key'),),
                )
            },
        )
        second = build_over(
            store,
            (OPENVERSE,),
            {
                OPENVERSE.id: FakeConnector(
                    OPENVERSE,
                    (
                        build_candidate(
                            candidate_id='openverse:1',
                            title='Genuine productivity suite, retail box',
                        ),
                    ),
                )
            },
        )

        await first.run(QUERY, run_id='run-1')
        await second.run(QUERY, run_id='run-2')
        stored = await store.pending_audit(1)

        assert stored[0].title == 'Windows license key'


class TestWhatDiscoveryStores:
    async def test_a_non_commercial_candidate_is_stored_without_a_rights_decision(self) -> None:
        connector = FakeConnector(
            OPENVERSE, (build_candidate(candidate_id='openverse:1', license_id='CC-BY-NC-4.0'),)
        )
        job, store = build_job((OPENVERSE,), {OPENVERSE.id: connector})

        run = await job.run(QUERY, run_id='run-1')

        assert run.persisted == 1
        assert store.decisions() == ()

    async def test_a_candidate_without_a_reported_licence_stores_an_absent_licence(self) -> None:
        connector = FakeConnector(
            OPENVERSE, (build_candidate(candidate_id='openverse:1', license_id=None),)
        )
        job, store = build_job((OPENVERSE,), {OPENVERSE.id: connector})

        await job.run(QUERY, run_id='run-1')
        stored = await store.pending_audit(1)

        assert stored[0].declared_license_id is None
        assert stored[0].declared_license_text is None

    async def test_a_stored_candidate_is_traceable_to_its_origin(self) -> None:
        connector = FakeConnector(
            OPENVERSE,
            (build_candidate(candidate_id='openverse:1', source_id=OPENVERSE.id),),
        )
        job, store = build_job((OPENVERSE,), {OPENVERSE.id: connector})

        await job.run(QUERY, run_id='run-1')
        stored = await store.pending_audit(1)

        assert stored[0].source_id == OPENVERSE.id
        assert stored[0].landing_url == 'https://openverse.test/items/openverse:1'


class TestBrokenSources:
    async def test_one_unavailable_source_does_not_lose_the_other_ones_candidates(self) -> None:
        working = FakeConnector(
            OPENVERSE, (build_candidate(candidate_id='openverse:1', license_id='CC0-1.0'),)
        )
        broken = FailingConnector(WIKIMEDIA, 'connection refused')
        job, store = build_job(
            (OPENVERSE, WIKIMEDIA), {OPENVERSE.id: working, WIKIMEDIA.id: broken}
        )

        run = await job.run(QUERY, run_id='run-1')

        assert run.persisted == 1
        assert store.stored_ids() == ('openverse:1',)
        assert len(run.failures) == 1
        assert run.failures[0].source_id == WIKIMEDIA.id
        assert 'connection refused' in run.failures[0].reason

    async def test_an_unreadable_payload_is_reported_as_a_failure_not_as_empty(self) -> None:
        unreadable = UnreadablePayloadConnector(WIKIMEDIA, ())
        job, store = build_job((WIKIMEDIA,), {WIKIMEDIA.id: unreadable})

        run = await job.run(QUERY, run_id='run-1')

        assert run.discovered == 0
        assert run.persisted == 0
        assert len(run.failures) == 1
        assert run.failures[0].source_id == WIKIMEDIA.id
        assert 'results' in run.failures[0].reason
        assert store.stored_ids() == ()
