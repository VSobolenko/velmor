from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from langgraph.graph.state import CompiledStateGraph

from packages.auditor.src.graph import AuditorGraph
from packages.auditor.src.state import AuditorState
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.interpretation import LicenseInterpretation
from packages.services.src.domain.review import HumanRuling
from packages.services.src.domain.rights import Evidence, RightsAction
from packages.services.src.domain.source import SourceSpec
from packages.services.src.rights.engine import RightsEngine
from packages.services.src.rights.license_grants import DefaultLicenseGrants
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.src.sources.source_registry import SourceRegistry
from packages.services.tests.conftest import FakeCredentials, build_spec

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

ESCALATION_CONFIDENCE = 0.5

NO_LICENSE_STATED = LicenseInterpretation(
    license_claim=None,
    confidence=0.0,
    quoted_text='',
    reasoning='the stub found no rights statement',
)


UNCERTAIN_INTERPRETATION = LicenseInterpretation(
    license_claim='MIT',
    confidence=0.2,
    quoted_text='possibly MIT licensed',
    reasoning='the page is ambiguous about reuse',
)
"""A reading the model is not sure of, which must never become a publication."""


class FixedClock:
    """Time held still, so a test asserts an exact timestamp."""

    def now(self) -> datetime:
        return NOW


class FakePageFetcher:
    """Stands in for the network: returns fixed text and records what it was asked for."""

    def __init__(self, text: str = 'no licence notice on this page') -> None:
        self._text = text
        self.fetched: list[str] = []

    async def fetch_text(self, url: str) -> str:
        self.fetched.append(url)
        return self._text


class FailingPageFetcher:
    """Stands in for a landing page that is gone: the fetch raises, as httpx does."""

    def __init__(self, error: httpx.HTTPError) -> None:
        self._error = error
        self.fetched: list[str] = []

    async def fetch_text(self, url: str) -> str:
        self.fetched.append(url)
        raise self._error


def gone_error(url: str) -> httpx.HTTPStatusError:
    """The error httpx raises when a landing page no longer exists."""
    request = httpx.Request('GET', url)
    return httpx.HTTPStatusError(
        'Client error 404 Not Found',
        request=request,
        response=httpx.Response(404, request=request),
    )


class FakeInterpreter:
    """Stands in for the model: returns a fixed reading and counts its calls."""

    def __init__(self, interpretation: LicenseInterpretation = NO_LICENSE_STATED) -> None:
        self._interpretation = interpretation
        self.calls: list[str] = []

    async def interpret(self, page_text: str, title: str) -> LicenseInterpretation:
        self.calls.append(title)
        return self._interpretation


class RecordingGraph:
    """Wraps a compiled graph and records which threads it was invoked for.

    Used where the assertion is that the graph was *not* reached: a decision
    saved anyway would look the same with or without a graph call.
    """

    def __init__(self, graph: CompiledStateGraph) -> None:
        self._graph = graph
        self.threads: list[str] = []

    async def ainvoke(self, state: AuditorState, config: dict) -> dict:
        self.threads.append(config['configurable']['thread_id'])
        return await self._graph.ainvoke(state, config)


def build_state(
    candidate: Candidate,
    spec: SourceSpec,
    evidence: tuple[Evidence, ...] = (),
    license_claim: str | None = None,
    resolved_license_id: str | None = None,
    interpretation: LicenseInterpretation | None = None,
    investigation_attempts: int = 0,
    investigation_failures: tuple[str, ...] = (),
    human_ruling: HumanRuling | None = None,
) -> AuditorState:
    return {
        'candidate': candidate,
        'source': spec,
        'evidence': list(evidence),
        'license_claim': license_claim,
        'resolved_license_id': resolved_license_id,
        'interpretation': interpretation,
        'investigation_attempts': investigation_attempts,
        'investigation_failures': list(investigation_failures),
        'human_ruling': human_ruling,
        'record': None,
        'decision': None,
    }


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def engine() -> RightsEngine:
    return RightsEngine(DefaultLicenseGrants.TABLE)


@pytest.fixture
def matrix(engine: RightsEngine) -> LicenseMatrix:
    return engine.matrix


@pytest.fixture
def registry() -> SourceRegistry:
    return SourceRegistry((build_spec(),), FakeCredentials())


@pytest.fixture
def compiled_graph(engine: RightsEngine, clock: FixedClock) -> CompiledStateGraph:
    """The real verification graph, with the model and the network faked out."""
    return AuditorGraph(
        engine=engine,
        fetcher=FakePageFetcher(),
        interpreter=FakeInterpreter(),
        clock=clock,
        model_name='test-model',
        max_investigation_attempts=1,
        escalation_confidence=ESCALATION_CONFIDENCE,
        requested_actions=RightsEngine.STOREFRONT_ACTIONS,
        checkpointer=None,
    ).build()


@pytest.fixture
def storefront_actions() -> tuple[RightsAction, ...]:
    return RightsEngine.STOREFRONT_ACTIONS
