from __future__ import annotations

from typing import Protocol

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.gate import GateDecision


class CandidateRepository(Protocol):
    """Storage for discovered candidates.

    Deliberately narrow: this interface writes candidates and reads back the ones
    with no verdict yet. It has no opinion about rights, so it can never become
    the place a publishability decision gets made by accident.
    """

    async def upsert_many(self, candidates: tuple[Candidate, ...]) -> int:
        """Store candidates, collapsing ones already known. Returns the count written."""
        ...

    async def pending_audit(self, limit: int) -> tuple[Candidate, ...]:
        """Candidates that have no rights record yet, oldest first."""
        ...


class RightsRecordRepository(Protocol):
    """Storage for verdicts, kept apart from candidate storage on purpose.

    Only the verification stage writes here, so the audit trail has exactly one
    author and a verdict can always be traced back to the run that produced it.
    """

    async def save(self, decision: GateDecision) -> None:
        """Persist a verdict, replacing any earlier one for the same candidate."""
        ...
