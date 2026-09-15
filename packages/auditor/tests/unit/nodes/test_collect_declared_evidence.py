from __future__ import annotations

from packages.auditor.src.nodes.collect_declared_evidence import CollectDeclaredEvidenceNode
from packages.auditor.tests.conftest import FixedClock, build_state
from packages.services.src.domain.rights import EvidenceKind
from packages.services.src.domain.source import SourceTier
from packages.services.tests.conftest import build_candidate, build_spec


class TestCollectDeclaredEvidenceNode:
    async def test_a_tier_a_declared_licence_is_recorded_as_source_evidence(
        self, clock: FixedClock
    ) -> None:
        node = CollectDeclaredEvidenceNode(clock)
        state = build_state(build_candidate(license_id='CC0-1.0'), build_spec())

        result = await node(state)

        evidence = result['evidence']
        assert len(evidence) == 1
        assert evidence[0].kind is EvidenceKind.SOURCE_API_FIELD
        assert evidence[0].excerpt == 'CC0-1.0'
        assert evidence[0].retrieved_at == clock.now()
        assert evidence[0].locator.endswith('item=openverse:1')

    async def test_a_tier_b_declared_licence_is_not_treated_as_machine_readable(
        self, clock: FixedClock
    ) -> None:
        node = CollectDeclaredEvidenceNode(clock)
        state = build_state(
            build_candidate(license_id='Some rights reserved'),
            build_spec(tier=SourceTier.B),
        )

        result = await node(state)

        assert result == {}

    async def test_a_candidate_without_a_declared_licence_records_nothing(
        self, clock: FixedClock
    ) -> None:
        node = CollectDeclaredEvidenceNode(clock)
        state = build_state(build_candidate(license_id=None), build_spec())

        result = await node(state)

        assert result == {}

    async def test_rerunning_the_node_does_not_duplicate_evidence(self, clock: FixedClock) -> None:
        node = CollectDeclaredEvidenceNode(clock)
        state = build_state(build_candidate(license_id='CC0-1.0'), build_spec())

        first = await node(state)
        second = await node(state)

        assert first == second
        assert len(second['evidence']) == 1
