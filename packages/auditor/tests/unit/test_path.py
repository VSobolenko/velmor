from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from packages.auditor.src.graph import AuditorGraph
from packages.auditor.src.runner import AuditorRunner
from packages.auditor.tests.conftest import (
    ESCALATION_CONFIDENCE,
    UNCERTAIN_INTERPRETATION,
    FakeInterpreter,
    FakePageFetcher,
    FixedClock,
)
from packages.scout.src.ingest import ScoutJob
from packages.services.src.connectors.contract import SourceConnector
from packages.services.src.domain.query import SearchQuery
from packages.services.src.domain.rights import RightsVerdict
from packages.services.src.domain.verification_run import VerificationOutcome
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.rights.engine import RightsEngine
from packages.services.src.screening.prohibited_screen import ProhibitedCategoryScreen
from packages.services.src.sources.source_registry import SourceRegistry
from packages.services.tests.conftest import (
    FailingConnector,
    FakeConnector,
    FakeConnectorFactory,
    FakeCredentials,
    build_candidate,
    build_spec,
)

QUERY = SearchQuery(text='vintage poster', limit=10)
BATCH_SIZE = 10
BROKEN = 'broken'


class TestVerificationPath:
    """The whole path: discovery stores a candidate, the pass rules on it.

    No network, no model, no database: the connector, the page fetch and the
    interpreter are substituted, and everything between them is the real code.
    """

    def build_discovery(
        self, store: InMemoryStore, connectors: dict[str, SourceConnector]
    ) -> ScoutJob:
        return ScoutJob(
            registry=SourceRegistry(
                tuple(connector.spec for connector in connectors.values()), FakeCredentials()
            ),
            factory=FakeConnectorFactory(connectors),
            repository=store,
        )

    def build_connectors(self, candidates: tuple, fail: bool = True) -> dict[str, SourceConnector]:
        spec = build_spec()
        connectors: dict[str, SourceConnector] = {
            spec.id: FakeConnector(spec, candidates),
        }
        if fail:
            connectors[BROKEN] = FailingConnector(build_spec(BROKEN), 'connection refused')
        return connectors

    def build_runner(
        self, engine: RightsEngine, clock: FixedClock, store: InMemoryStore
    ) -> AuditorRunner:
        return AuditorRunner(
            compiled_graph=AuditorGraph(
                engine=engine,
                fetcher=FakePageFetcher(),
                interpreter=FakeInterpreter(),
                clock=clock,
                model_name='test-model',
                max_investigation_attempts=1,
                escalation_confidence=ESCALATION_CONFIDENCE,
                requested_actions=RightsEngine.STOREFRONT_ACTIONS,
                checkpointer=None,
            ).build(),
            registry=SourceRegistry((build_spec(),), FakeCredentials()),
            screen=ProhibitedCategoryScreen(),
            candidates=store,
            verdicts=store,
            batch_size=BATCH_SIZE,
        )

    async def test_a_commercial_item_is_published_and_a_non_commercial_one_is_refused(
        self, engine: RightsEngine, clock: FixedClock
    ) -> None:
        store = InMemoryStore()
        connectors = self.build_connectors(
            (
                build_candidate(candidate_id='openverse:1', license_id='CC0-1.0'),
                build_candidate(candidate_id='openverse:2', license_id='CC-BY-NC-4.0'),
            )
        )

        discovered = await self.build_discovery(store, connectors).run(QUERY, run_id='run-1')
        run = await self.build_runner(engine, clock, store).run_once()

        assert discovered.discovered == 2
        assert connectors['openverse'].queries == [QUERY]
        published, refused = run.outcomes
        assert published.outcome is VerificationOutcome.PUBLISHED
        assert published.decision.publishable is True
        assert refused.outcome is VerificationOutcome.REFUSED
        assert refused.decision.publishable is False
        assert refused.reasons
        assert store.publishable_ids() == ('openverse:1',)

    async def test_the_refusal_names_the_licence_concern(
        self, engine: RightsEngine, clock: FixedClock
    ) -> None:
        store = InMemoryStore()
        connectors = self.build_connectors(
            (build_candidate(candidate_id='openverse:2', license_id='CC-BY-NC-4.0'),), fail=False
        )

        await self.build_discovery(store, connectors).run(QUERY, run_id='run-1')
        run = await self.build_runner(engine, clock, store).run_once()

        outcome = run.outcomes[0]
        assert 'CC-BY-NC-4.0' in ' '.join(outcome.reasons)
        assert outcome.decision.record.verdict is RightsVerdict.DENIED

    async def test_a_second_pass_over_the_same_items_rules_on_nothing_new(
        self, engine: RightsEngine, clock: FixedClock
    ) -> None:
        store = InMemoryStore()
        connector = FakeConnector(
            build_spec(), (build_candidate(candidate_id='openverse:1', license_id='CC0-1.0'),)
        )
        job = self.build_discovery(store, {'openverse': connector})

        first_discovery = await job.run(QUERY, run_id='run-1')
        first_pass = await self.build_runner(engine, clock, store).run_once()
        second_discovery = await job.run(QUERY, run_id='run-2')
        second_pass = await self.build_runner(engine, clock, store).run_once()

        assert first_discovery.persisted == 1
        assert second_discovery.discovered == 1
        assert second_discovery.persisted == 0
        assert store.stored_ids() == ('openverse:1',)
        assert len(first_pass.outcomes) == 1
        assert second_pass.outcomes == ()

    async def test_a_broken_source_does_not_lose_the_other_ones_candidates(
        self, engine: RightsEngine, clock: FixedClock
    ) -> None:
        store = InMemoryStore()
        connectors = self.build_connectors(
            (build_candidate(candidate_id='openverse:1', license_id='CC0-1.0'),)
        )

        run = await self.build_discovery(store, connectors).run(QUERY, run_id='run-1')
        verified = await self.build_runner(engine, clock, store).run_once()

        assert run.failures[0].source_id == BROKEN
        assert 'connection refused' in run.failures[0].reason
        assert [outcome.outcome for outcome in verified.outcomes] == [VerificationOutcome.PUBLISHED]

    async def test_a_hesitant_model_reading_is_escalated_instead_of_published(
        self, engine: RightsEngine, clock: FixedClock
    ) -> None:
        store = InMemoryStore()
        connectors = self.build_connectors(
            (build_candidate(candidate_id='openverse:1', license_id=None),), fail=False
        )
        job = self.build_discovery(store, connectors)
        await job.run(QUERY, run_id='run-1')

        runner = AuditorRunner(
            compiled_graph=AuditorGraph(
                engine=engine,
                fetcher=FakePageFetcher('possibly MIT licensed'),
                interpreter=FakeInterpreter(UNCERTAIN_INTERPRETATION),
                clock=clock,
                model_name='test-model',
                max_investigation_attempts=1,
                escalation_confidence=ESCALATION_CONFIDENCE,
                requested_actions=RightsEngine.STOREFRONT_ACTIONS,
                checkpointer=InMemorySaver(),
            ).build(),
            registry=SourceRegistry((build_spec(),), FakeCredentials()),
            screen=ProhibitedCategoryScreen(),
            candidates=store,
            verdicts=store,
            batch_size=BATCH_SIZE,
        )

        run = await runner.run_once()

        assert run.outcomes[0].outcome is VerificationOutcome.PAUSED
        assert run.outcomes[0].decision is None
        assert store.decisions() == ()
        assert store.publishable_ids() == ()

    async def test_a_relisted_candidate_is_refused_again(
        self, engine: RightsEngine, clock: FixedClock
    ) -> None:
        store = InMemoryStore()
        spec = build_spec()
        first = FakeConnector(
            spec, (build_candidate(candidate_id='openverse:1', title='Windows license key'),)
        )
        await self.build_discovery(store, {spec.id: first}).run(QUERY, run_id='run-1')
        runner = self.build_runner(engine, clock, store)
        refused = await runner.run_once()

        reworded = FakeConnector(
            spec, (build_candidate(candidate_id='openverse:1', title='Retail office suite'),)
        )
        await self.build_discovery(store, {spec.id: reworded}).run(QUERY, run_id='run-2')
        refused_again = await runner.run_once()

        assert refused.outcomes[0].outcome is VerificationOutcome.SCREENED_OUT
        assert refused_again.outcomes[0].outcome is VerificationOutcome.SCREENED_OUT
        assert store.decisions() == ()
