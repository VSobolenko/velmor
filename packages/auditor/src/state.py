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
    """

    candidate: Candidate
    source: SourceSpec
    evidence: list[Evidence]
    resolved_license_id: str | None
    interpretation: LicenseInterpretation | None
    investigation_attempts: int
    human_ruling: HumanRuling | None
    record: RightsRecord | None
    decision: GateDecision | None
