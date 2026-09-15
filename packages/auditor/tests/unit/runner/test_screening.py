from __future__ import annotations

import pytest
from langgraph.graph.state import CompiledStateGraph

from packages.auditor.src.runner import AuditorRunner
from packages.auditor.tests.conftest import RecordingGraph
from packages.services.src.domain.verification_run import VerificationOutcome
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.screening.prohibited_screen import ProhibitedCategoryScreen
from packages.services.src.sources.source_registry import SourceRegistry
from packages.services.tests.conftest import (
    FakeCredentials,
    build_candidate,
    build_spec,
)

BATCH_SIZE = 10


def build_runner(
    graph: CompiledStateGraph,
    registry: SourceRegistry,
    store: InMemoryStore,
) -> AuditorRunner:
    return AuditorRunner(
        compiled_graph=graph,
        registry=registry,
        screen=ProhibitedCategoryScreen(),
        candidates=store,
        verdicts=store,
        batch_size=BATCH_SIZE,
    )


class TestScreening:
    @pytest.mark.parametrize(
        'title',
        [
            'Cheap Windows license key',
            'CHEAP WINDOWS LICENSE KEY - limited offer',
            'Original software activation key, bundled with tutorials',
        ],
    )
    async def test_a_prohibited_candidate_is_refused_before_the_graph(
        self,
        title: str,
        compiled_graph: CompiledStateGraph,
        registry: SourceRegistry,
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many((build_candidate(license_id='CC0-1.0', title=title),))
        graph = RecordingGraph(compiled_graph)

        run = await build_runner(graph, registry, store).run_once()

        outcome = run.outcomes[0]
        assert outcome.outcome is VerificationOutcome.SCREENED_OUT
        assert outcome.reasons
        assert outcome.decision is None
        assert graph.threads == []
        assert store.decisions() == ()

    async def test_a_refusal_names_the_category_that_matched(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            (build_candidate(license_id='CC0-1.0', title='Windows license key'),)
        )

        run = await build_runner(RecordingGraph(compiled_graph), registry, store).run_once()

        assert 'license key' in run.outcomes[0].reasons[0]
        assert run.refusals_by_category[0].category == 'license key'

    async def test_a_clear_candidate_reaches_the_graph_unchanged(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        candidate = build_candidate(license_id='CC0-1.0')
        store = InMemoryStore()
        await store.upsert_many((candidate,))
        graph = RecordingGraph(compiled_graph)

        run = await build_runner(graph, registry, store).run_once()

        assert run.outcomes[0].outcome is VerificationOutcome.PUBLISHED
        assert graph.threads == [candidate.id]
        assert run.refusals_by_category == ()

    async def test_a_refused_candidate_does_not_stop_the_batch(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        forbidden = build_candidate(
            candidate_id='openverse:1', license_id='CC0-1.0', title='Steam key bundle'
        )
        allowed = build_candidate(candidate_id='openverse:2', license_id='CC0-1.0')
        store = InMemoryStore()
        await store.upsert_many((forbidden, allowed))
        graph = RecordingGraph(compiled_graph)

        run = await build_runner(graph, registry, store).run_once()

        assert [outcome.outcome for outcome in run.outcomes] == [
            VerificationOutcome.SCREENED_OUT,
            VerificationOutcome.PUBLISHED,
        ]
        assert graph.threads == [allowed.id]

    async def test_a_screened_out_candidate_gets_no_rights_record(
        self, compiled_graph: CompiledStateGraph, registry: SourceRegistry
    ) -> None:
        store = InMemoryStore()
        await store.upsert_many(
            (build_candidate(license_id='CC0-1.0', title='Cracked photo editor'),)
        )

        await build_runner(RecordingGraph(compiled_graph), registry, store).run_once()

        assert store.decisions() == ()
        assert store.publishable_ids() == ()

    async def test_the_source_registry_is_not_consulted_for_a_refused_candidate(
        self, compiled_graph: CompiledStateGraph
    ) -> None:
        unregistered = build_candidate(
            source_id='unregistered', license_id='CC0-1.0', title='Activation key'
        )
        store = InMemoryStore()
        await store.upsert_many((unregistered,))
        registry = SourceRegistry((build_spec(),), FakeCredentials())

        run = await build_runner(RecordingGraph(compiled_graph), registry, store).run_once()

        assert run.outcomes[0].outcome is VerificationOutcome.SCREENED_OUT
