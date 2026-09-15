from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from packages.auditor.src.node_names import (
    COLLECT_DECLARED_EVIDENCE,
    DECIDE,
    INVESTIGATE,
    RESOLVE_LICENSE,
    REVIEW,
)
from packages.auditor.src.nodes import (
    CollectDeclaredEvidenceNode,
    DecideNode,
    InvestigateNode,
    ResolutionRouter,
    ResolveLicenseNode,
    ReviewNode,
)
from packages.auditor.src.state import AuditorState
from packages.services.src.clock import Clock
from packages.services.src.domain.rights import RightsAction
from packages.services.src.http_service.page_fetcher import PageFetcher
from packages.services.src.llm.license_interpreter import LicenseInterpreter
from packages.services.src.rights.engine import RightsEngine


class AuditorGraph:
    """Assemble the rights-verification graph.

    Shape::

        collect_declared_evidence -> resolve_license -+-> decide -> END
                                                      |
                                       investigate <--+   (loop while attempts remain)
                                                      |
                                             review --+   (human fallback)

    The loop is why this is a graph and not a function. A tier A item usually
    resolves on the first pass and never costs a model call; an ambiguous one is
    investigated, re-resolved, and either settles, escalates to a person because
    the model is unsure of what it read, or escalates because the attempts ran
    out. Those decisions come from accumulated state, and the checkpointer makes
    a long investigation resumable instead of restartable.
    """

    def __init__(
        self,
        engine: RightsEngine,
        fetcher: PageFetcher,
        interpreter: LicenseInterpreter,
        clock: Clock,
        model_name: str,
        max_investigation_attempts: int,
        escalation_confidence: float,
        requested_actions: tuple[RightsAction, ...],
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self._engine = engine
        self._fetcher = fetcher
        self._interpreter = interpreter
        self._clock = clock
        self._model_name = model_name
        self._max_investigation_attempts = max_investigation_attempts
        self._escalation_confidence = escalation_confidence
        self._requested_actions = requested_actions
        self._checkpointer = checkpointer

    def build(self) -> CompiledStateGraph:
        graph: StateGraph = StateGraph(AuditorState)

        graph.add_node(COLLECT_DECLARED_EVIDENCE, CollectDeclaredEvidenceNode(self._clock))
        graph.add_node(RESOLVE_LICENSE, ResolveLicenseNode(self._engine.matrix, self._clock))
        graph.add_node(
            INVESTIGATE,
            InvestigateNode(self._fetcher, self._interpreter, self._clock, self._model_name),
        )
        graph.add_node(REVIEW, ReviewNode(self._engine.matrix, self._clock))
        graph.add_node(
            DECIDE,
            DecideNode(
                self._engine.resolver, self._engine.gate, self._clock, self._requested_actions
            ),
        )

        graph.add_edge(START, COLLECT_DECLARED_EVIDENCE)
        graph.add_edge(COLLECT_DECLARED_EVIDENCE, RESOLVE_LICENSE)
        graph.add_conditional_edges(
            RESOLVE_LICENSE,
            ResolutionRouter(self._max_investigation_attempts, self._escalation_confidence),
            {
                DECIDE: DECIDE,
                INVESTIGATE: INVESTIGATE,
                REVIEW: REVIEW,
            },
        )
        graph.add_edge(INVESTIGATE, RESOLVE_LICENSE)
        graph.add_edge(REVIEW, DECIDE)
        graph.add_edge(DECIDE, END)

        return graph.compile(checkpointer=self._checkpointer)
