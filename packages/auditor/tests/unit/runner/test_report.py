from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from packages.auditor.src.graph import AuditorGraph
from packages.auditor.src.runner import AuditorRunner
from packages.auditor.tests.conftest import (
    ESCALATION_CONFIDENCE,
    FailingPageFetcher,
    FakeInterpreter,
    FakePageFetcher,
    FixedClock,
    gone_error,
)
from packages.services.src.domain.verification_run import VerificationOutcome
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.rights.engine import RightsEngine
from packages.services.src.screening.prohibited_screen import ProhibitedCategoryScreen
from packages.services.src.sources.source_registry import SourceRegistry
from packages.services.tests.conftest import build_candidate

BATCH_SIZE = 10

GONE = gone_error('https://openverse.test/items/openverse:1')


def build_runner(
    graph: CompiledStateGraph,
    registry: SourceRegistry,
    store: InMemoryStore,
    batch_size: int = BATCH_SIZE,
) -> AuditorRunner:
    return AuditorRunner(
        compiled_graph=graph,
        registry=registry,
        screen=ProhibitedCategoryScreen(),
        candidates=store,
        verdicts=store,
        batch_size=batch_size,
    )


class TestVerificationRunReport:
    async def test_every_candidate_in_the_batch_appears_once(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            (
                build_candidate(candidate_id='openverse:1', license_id='CC0-1.0'),
                build_candidate(
                    candidate_id='openverse:2',
                    license_id='CC0-1.0',
                    title='Windows license key',
                ),
                build_candidate(candidate_id='openverse:3', license_id='CC-BY-NC-4.0'),
            )
        )

        run = await build_runner(compiled_graph, registry, store).run_once()

        assert [outcome.candidate_id for outcome in run.outcomes] == [
            'openverse:1',
            'openverse:2',
            'openverse:3',
        ]
        assert len({outcome.candidate_id for outcome in run.outcomes}) == 3

    async def test_three_refusals_out_of_ten_leave_seven_verified(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            (
                build_candidate(candidate_id='openverse:1', title='Windows license key'),
                build_candidate(candidate_id='openverse:2', title='Cracked photo editor'),
                build_candidate(candidate_id='openverse:3', title='Gift card voucher code'),
                *(
                    build_candidate(candidate_id=f'openverse:{index}', license_id='CC0-1.0')
                    for index in range(4, 11)
                ),
            )
        )

        run = await build_runner(compiled_graph, registry, store).run_once()

        refused = [o for o in run.outcomes if o.outcome is VerificationOutcome.SCREENED_OUT]
        verified = [o for o in run.outcomes if o.outcome is not VerificationOutcome.SCREENED_OUT]
        counted = sum(refusal.count for refusal in run.refusals_by_category)
        assert len(refused) == 3
        assert len(verified) == 7
        assert counted == 4
        assert [refusal.category for refusal in run.refusals_by_category] == [
            'crack',
            'gift card',
            'license key',
            'voucher code',
        ]
        assert store.publishable_ids() == tuple(f'openverse:{index}' for index in range(4, 11))

    async def test_a_batch_of_ten_verifies_all_of_them(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            tuple(
                build_candidate(candidate_id=f'openverse:{index}', license_id='CC0-1.0')
                for index in range(10)
            )
        )

        run = await build_runner(compiled_graph, registry, store).run_once()

        assert len(run.outcomes) == 10

    async def test_a_batch_size_bounds_the_pass(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            tuple(
                build_candidate(candidate_id=f'openverse:{index}', license_id='CC0-1.0')
                for index in range(5)
            )
        )

        run = await build_runner(compiled_graph, registry, store, batch_size=2).run_once()

        assert len(run.outcomes) == 2

    async def test_a_ruled_candidate_is_not_verified_again(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many((build_candidate(license_id='CC0-1.0'),))
        runner = build_runner(compiled_graph, registry, store)

        first = await runner.run_once()
        second = await runner.run_once()

        assert [outcome.outcome for outcome in first.outcomes] == [VerificationOutcome.PUBLISHED]
        assert second.outcomes == ()

    async def test_a_paused_candidate_is_reported_as_paused_and_does_not_stop_the_batch(
        self, engine: RightsEngine, clock: FixedClock, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            (
                build_candidate(candidate_id='openverse:1', license_id=None),
                build_candidate(candidate_id='openverse:2', license_id='CC0-1.0'),
            )
        )
        graph = self.build_pausing_graph(engine, clock)

        run = await build_runner(graph, registry, store).run_once()

        paused, published = run.outcomes
        assert paused.outcome is VerificationOutcome.PAUSED
        assert paused.decision is None
        assert paused.reasons
        assert published.outcome is VerificationOutcome.PUBLISHED
        assert store.publishable_ids() == ('openverse:2',)

    async def test_a_paused_candidate_stays_in_the_next_batch(
        self, engine: RightsEngine, clock: FixedClock, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        candidate = build_candidate(license_id=None)
        await store.upsert_many((candidate,))
        graph = self.build_pausing_graph(engine, clock)

        run = await build_runner(graph, registry, store).run_once()

        assert run.outcomes[0].outcome is VerificationOutcome.PAUSED
        assert await store.pending_audit(10) == (candidate,)

    @staticmethod
    def build_pausing_graph(
        engine: RightsEngine,
        clock: FixedClock,
        fetcher: FakePageFetcher | FailingPageFetcher | None = None,
    ) -> CompiledStateGraph:
        """The real graph with a checkpointer, so an unresolved licence can pause."""
        return AuditorGraph(
            engine=engine,
            fetcher=FakePageFetcher() if fetcher is None else fetcher,
            interpreter=FakeInterpreter(),
            clock=clock,
            model_name='test-model',
            max_investigation_attempts=1,
            escalation_confidence=ESCALATION_CONFIDENCE,
            requested_actions=RightsEngine.STOREFRONT_ACTIONS,
            checkpointer=InMemorySaver(),
        ).build()

    async def test_a_dead_page_is_reported_with_the_reason_it_paused(
        self, engine: RightsEngine, clock: FixedClock, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many((build_candidate(license_id=None),))
        graph = self.build_pausing_graph(engine, clock, FailingPageFetcher(GONE))

        run = await build_runner(graph, registry, store).run_once()

        paused = run.outcomes[0]
        assert paused.outcome is VerificationOutcome.PAUSED
        assert paused.reasons[0] == AuditorRunner.PAUSED_REASON
        assert any('fetch failed' in reason for reason in paused.reasons)
