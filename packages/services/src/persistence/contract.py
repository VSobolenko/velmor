from __future__ import annotations

from typing import Protocol

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.rights import RightsRecord


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


class StorefrontCatalog(Protocol):
    """Read model for the storefront: the goods the gate published.

    Separate from the write repositories because it answers a different question.
    Nothing here decides anything: a good is reachable only through
    ``publishable``, so there is no query the storefront could issue that would
    list something the gate refused. Selling the good is not this interface's
    concern either - it carries the record so the page can state the licence and
    the obligations that came with the verdict.
    """

    async def published(self, limit: int) -> tuple[tuple[Candidate, RightsRecord], ...]:
        """Publishable goods, most recently decided first."""
        ...

    async def published_count(self) -> int:
        """How many publishable goods exist in total.

        Separate from the length of ``published``: that list is capped, and a page
        that reported the cap as the size of the catalogue would be stating
        something false about the business.
        """
        ...
