from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from packages.auditor.src.node_names import REVIEW
from packages.auditor.src.nodes.decide import DecideNode
from packages.auditor.src.nodes.review import ReviewNode
from packages.auditor.src.state import AuditorState
from packages.auditor.tests.conftest import FixedClock, build_state
from packages.services.src.domain.rights import EvidenceKind
from packages.services.src.rights.engine import RightsEngine
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.tests.conftest import build_candidate, build_spec

THREAD = {'configurable': {'thread_id': 'review-node-test'}}


class TestReviewNode:
    """ReviewNode is tested inside a graph because ``interrupt`` only exists in one.

    The graph holds this node alone, so what is asserted is still the node: its
    request payload, what it records on approval, and what it refuses to record.
    """

    def build_node_graph(self, matrix: LicenseMatrix, clock: FixedClock) -> CompiledStateGraph:
        graph: StateGraph = StateGraph(AuditorState)
        graph.add_node(REVIEW, ReviewNode(matrix, clock))
        graph.add_edge(START, REVIEW)
        graph.add_edge(REVIEW, END)
        return graph.compile(checkpointer=InMemorySaver())

    def build_state_for_review(self) -> AuditorState:
        return build_state(build_candidate(license_id=None), build_spec())

    async def test_the_run_pauses_and_asks_which_licence_applies(
        self, matrix: LicenseMatrix, clock: FixedClock
    ) -> None:
        app = self.build_node_graph(matrix, clock)

        paused = await app.ainvoke(self.build_state_for_review(), config=THREAD)

        interrupt = paused['__interrupt__'][0]
        assert interrupt.value['candidate_id'] == 'openverse:1'
        assert interrupt.value['declared_license_id'] is None
        assert interrupt.value['question'] == 'Which licence applies to this item, if any?'
        assert paused['decision'] is None

    async def test_an_approved_ruling_records_attestation_and_identity_match(
        self, matrix: LicenseMatrix, clock: FixedClock
    ) -> None:
        app = self.build_node_graph(matrix, clock)
        await app.ainvoke(self.build_state_for_review(), config=THREAD)

        resumed = await app.ainvoke(
            Command(resume={'approved': True, 'license_id': 'MIT', 'note': 'checked by hand'}),
            config=THREAD,
        )

        assert [item.kind for item in resumed['evidence']] == [
            EvidenceKind.HUMAN_ATTESTATION,
            EvidenceKind.SPDX_MATCH,
        ]
        assert resumed['resolved_license_id'] == 'MIT'
        assert resumed['human_ruling'].approved is True

    async def test_a_rejected_ruling_records_no_licence(
        self, matrix: LicenseMatrix, clock: FixedClock
    ) -> None:
        app = self.build_node_graph(matrix, clock)
        await app.ainvoke(self.build_state_for_review(), config=THREAD)

        resumed = await app.ainvoke(
            Command(resume={'approved': False, 'license_id': None, 'note': 'not reusable'}),
            config=THREAD,
        )

        assert resumed['human_ruling'].approved is False
        assert resumed['evidence'] == []
        assert resumed['resolved_license_id'] is None

    async def test_an_approved_ruling_for_an_unknown_licence_resolves_nothing(
        self, matrix: LicenseMatrix, clock: FixedClock
    ) -> None:
        app = self.build_node_graph(matrix, clock)
        await app.ainvoke(self.build_state_for_review(), config=THREAD)

        resumed = await app.ainvoke(
            Command(
                resume={
                    'approved': True,
                    'license_id': 'Velmor-Internal-Ware',
                    'note': 'we wrote it ourselves',
                }
            ),
            config=THREAD,
        )

        assert [item.kind for item in resumed['evidence']] == [
            EvidenceKind.HUMAN_ATTESTATION,
        ]
        assert resumed['resolved_license_id'] is None

    async def test_an_approval_cannot_widen_what_a_licence_permits(
        self, matrix: LicenseMatrix, clock: FixedClock, engine: RightsEngine
    ) -> None:
        app = self.build_node_graph(matrix, clock)
        await app.ainvoke(self.build_state_for_review(), config=THREAD)

        resumed = await app.ainvoke(
            Command(
                resume={
                    'approved': True,
                    'license_id': 'CC-BY-NC-4.0',
                    'note': 'this is the licence shown on the page',
                }
            ),
            config=THREAD,
        )

        assert resumed['resolved_license_id'] == 'CC-BY-NC-4.0'

        decide = DecideNode(engine.resolver, engine.gate, clock, RightsEngine.STOREFRONT_ACTIONS)
        ruled = await decide(resumed)

        assert ruled['decision'].publishable is False
        assert ruled['decision'].reasons
