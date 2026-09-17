from __future__ import annotations

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.rights import RightsRecord


class InMemoryStore:
    """Candidate and verdict storage held in process memory, for tests and dry runs.

    It implements both repository protocols, as ``PostgresStore`` does, because
    the two are one contract in practice: ``pending_audit`` is an anti-join
    against the verdicts. A double that kept candidates and verdicts in separate
    objects would hand the auditor every candidate it had already decided, and a
    test written against it would prove behaviour the production store does not
    have.

    Insertion order is preserved so ``pending_audit`` is deterministic, which is
    what lets a test assert the order the auditor will process a batch in.
    """

    def __init__(self) -> None:
        self._candidates: dict[str, Candidate] = {}
        self._decisions: dict[str, GateDecision] = {}

    async def upsert_many(self, candidates: tuple[Candidate, ...]) -> int:
        written = 0
        for candidate in candidates:
            if candidate.id in self._candidates:
                continue
            self._candidates[candidate.id] = candidate
            written += 1
        return written

    async def pending_audit(self, limit: int) -> tuple[Candidate, ...]:
        pending = [
            candidate
            for candidate_id, candidate in self._candidates.items()
            if candidate_id not in self._decisions
        ]
        return tuple(pending[:limit])

    async def save(self, decision: GateDecision) -> None:
        self._decisions[decision.candidate_id] = decision

    async def published(self, limit: int) -> tuple[tuple[Candidate, RightsRecord], ...]:
        return tuple(
            (self._candidates[candidate_id], decision.record)
            for candidate_id, decision in self._decisions.items()
            if decision.publishable and candidate_id in self._candidates
        )[:limit]

    async def published_count(self) -> int:
        return sum(
            1
            for candidate_id, decision in self._decisions.items()
            if decision.publishable and candidate_id in self._candidates
        )

    def stored_ids(self) -> tuple[str, ...]:
        return tuple(self._candidates)

    def decisions(self) -> tuple[GateDecision, ...]:
        return tuple(self._decisions.values())

    def publishable_ids(self) -> tuple[str, ...]:
        return tuple(
            candidate_id
            for candidate_id, decision in self._decisions.items()
            if decision.publishable
        )
