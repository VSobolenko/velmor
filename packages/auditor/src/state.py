from __future__ import annotations

from typing import TypedDict

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.interpretation import LicenseInterpretation
from packages.services.src.domain.review import HumanRuling
from packages.services.src.domain.rights import Evidence, RightsRecord
from packages.services.src.domain.source import SourceSpec


class AuditorState(TypedDict):
    """Everything the verification graph carries between nodes.

    ``evidence`` is a plain list rather than a reducer channel: each node returns
    the full list it computed from the list it received. That keeps every node
    safe to re-run, which matters because LangGraph restarts an interrupted node
    from the top when it resumes - a node appending to a shared list would
    double-count.

    ``license_claim`` and ``resolved_license_id`` are the two facts about the
    license identity, kept apart on purpose: the first is the claim the run
    settled on - a human ruling, a model reading or the source's own field - and
    the second is that claim mapped onto the policy table, or ``None`` when it
    maps to nothing. The router reads the resolution to decide where to go next,
    and the decision reads the claim so it can name it in the record even when it
    resolved to nothing.
    """

    candidate: Candidate
    source: SourceSpec
    evidence: list[Evidence]
    license_claim: str | None
    resolved_license_id: str | None
    interpretation: LicenseInterpretation | None
    investigation_attempts: int
    human_ruling: HumanRuling | None
    record: RightsRecord | None
    decision: GateDecision | None
