from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from packages.services.src.domain.gate import GateDecision


class VerificationOutcome(StrEnum):
    """How one candidate's verification ended.

    Four values rather than two, because a refusal the gate made and a candidate
    that never reached the gate are different facts. A screened-out candidate has
    no rights record at all, and a paused one has no ruling yet, so reporting
    either as a refusal would assert a decision nobody made.
    """

    PUBLISHED = 'published'
    REFUSED = 'refused'
    SCREENED_OUT = 'screened_out'
    PAUSED = 'paused'


class CandidateOutcome(BaseModel):
    """What one pass did with one candidate.

    ``decision`` is present only for the two outcomes the gate ruled on. It is a
    required field rather than an optional one with a default, so a producer has
    to state which of the four outcomes it means instead of leaving the question
    open.
    """

    model_config = {'frozen': True}

    candidate_id: str
    outcome: VerificationOutcome
    reasons: tuple[str, ...]
    decision: GateDecision | None


class CategoryRefusal(BaseModel):
    """How many candidates one prohibited category removed during a pass."""

    model_config = {'frozen': True}

    category: str
    count: int


class VerificationRun(BaseModel):
    """Outcome of one verification pass, with one entry per candidate it touched.

    A pass that reports only its publishable items hides everything it discarded,
    which is how a category of loss becomes a surprise later. This report carries
    every candidate the pass selected, in the order it selected them.
    """

    model_config = {'frozen': True}

    run_id: str
    outcomes: tuple[CandidateOutcome, ...]
    refusals_by_category: tuple[CategoryRefusal, ...]
