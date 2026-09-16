from __future__ import annotations

import uuid
from collections import Counter

from langgraph.graph.state import CompiledStateGraph

from packages.auditor.src.state import AuditorState
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.screening import ScreeningResult
from packages.services.src.domain.source import SourceSpec
from packages.services.src.domain.verification_run import (
    CandidateOutcome,
    CategoryRefusal,
    VerificationOutcome,
    VerificationRun,
)
from packages.services.src.persistence.contract import (
    CandidateRepository,
    RightsRecordRepository,
)
from packages.services.src.screening.prohibited_screen import ProhibitedCategoryScreen
from packages.services.src.sources.source_registry import SourceRegistry


class AuditorRunner:
    """Verify every candidate that has no verdict yet.

    Each candidate runs in its own thread, so one long investigation cannot block
    or corrupt another. A run that pauses for human review returns no decision
    here and is picked up again once the ruling arrives.

    Screening happens here rather than inside the graph: a candidate in a
    prohibited category has no licence question to answer, so putting the screen
    in the graph would mean either inventing a verdict for it or threading a
    second decision type through the state.
    """

    PAUSED_REASON = 'Awaiting human review: no publication decision yet'

    SCREENED_OUT_REASON = 'Prohibited category matched'

    def __init__(
        self,
        compiled_graph: CompiledStateGraph,
        registry: SourceRegistry,
        screen: ProhibitedCategoryScreen,
        candidates: CandidateRepository,
        verdicts: RightsRecordRepository,
        batch_size: int,
    ) -> None:
        self._graph = compiled_graph
        self._registry = registry
        self._screen = screen
        self._candidates = candidates
        self._verdicts = verdicts
        self._batch_size = batch_size

    async def run_once(self) -> VerificationRun:
        candidates = await self._candidates.pending_audit(self._batch_size)
        screenings = tuple(self._screen.screen(candidate) for candidate in candidates)

        outcomes = []
        for candidate, screening in zip(candidates, screenings, strict=True):
            outcomes.append(await self._outcome_for(candidate, screening))

        return VerificationRun(
            run_id=str(uuid.uuid4()),
            outcomes=tuple(outcomes),
            refusals_by_category=self._refusal_counts(screenings),
        )

    async def verify(self, candidate: Candidate) -> GateDecision | None:
        spec = self._registry.by_id(candidate.source_id)
        result = await self._graph.ainvoke(
            self._initial_state(candidate, spec),
            config={'configurable': {'thread_id': candidate.id}},
        )
        # A paused run has produced no verdict yet. That is neither a failure nor
        # a rejection, so it is reported as absent rather than as a decision.
        decision = result.get('decision')
        return decision if isinstance(decision, GateDecision) else None

    async def _outcome_for(
        self, candidate: Candidate, screening: ScreeningResult
    ) -> CandidateOutcome:
        if not screening.clear:
            return self._screened_out(candidate, screening)
        return await self._ruled(candidate)

    async def _ruled(self, candidate: Candidate) -> CandidateOutcome:
        decision = await self.verify(candidate)
        if decision is None:
            return CandidateOutcome(
                candidate_id=candidate.id,
                outcome=VerificationOutcome.PAUSED,
                reasons=(self.PAUSED_REASON,),
                decision=None,
            )

        await self._verdicts.save(decision)
        return CandidateOutcome(
            candidate_id=candidate.id,
            outcome=(
                VerificationOutcome.PUBLISHED
                if decision.publishable
                else VerificationOutcome.REFUSED
            ),
            reasons=decision.reasons,
            decision=decision,
        )

    def _screened_out(self, candidate: Candidate, screening: ScreeningResult) -> CandidateOutcome:
        return CandidateOutcome(
            candidate_id=candidate.id,
            outcome=VerificationOutcome.SCREENED_OUT,
            reasons=tuple(
                f'{self.SCREENED_OUT_REASON}: {category}' for category in screening.violations
            ),
            decision=None,
        )

    @staticmethod
    def _refusal_counts(
        screenings: tuple[ScreeningResult, ...],
    ) -> tuple[CategoryRefusal, ...]:
        counts: Counter[str] = Counter()
        for screening in screenings:
            counts.update(screening.violations)
        return tuple(
            CategoryRefusal(category=category, count=count)
            for category, count in sorted(counts.items())
        )

    @staticmethod
    def _initial_state(candidate: Candidate, spec: SourceSpec) -> AuditorState:
        return {
            'candidate': candidate,
            'source': spec,
            'evidence': [],
            'license_claim': None,
            'resolved_license_id': None,
            'interpretation': None,
            'investigation_attempts': 0,
            'human_ruling': None,
            'record': None,
            'decision': None,
        }
