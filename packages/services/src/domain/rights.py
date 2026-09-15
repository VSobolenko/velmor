from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class RightsAction(StrEnum):
    """A thing the platform intends to do with a good.

    These are the questions the license matrix answers. ``RESELL`` is separated
    from ``REDISTRIBUTE`` on purpose: selling access to a copy and handing out
    unencumbered copies are different acts with different license consequences.
    """

    RESELL = 'resell'
    REDISTRIBUTE = 'redistribute'
    MODIFY = 'modify'
    SUBLICENSE = 'sublicense'


class RightsVerdict(StrEnum):
    ALLOWED = 'allowed'
    DENIED = 'denied'
    UNKNOWN = 'unknown'


class EvidenceKind(StrEnum):
    """Where a rights fact came from, so a verdict can be audited later."""

    SOURCE_API_FIELD = 'source_api_field'
    LICENSE_FILE = 'license_file'
    SPDX_MATCH = 'spdx_match'
    LLM_EXTRACTION = 'llm_extraction'
    HUMAN_ATTESTATION = 'human_attestation'


class Evidence(BaseModel):
    """One auditable observation supporting a rights fact.

    ``excerpt`` is stored verbatim. An LLM reading is never sufficient on its
    own: the publication gate requires at least one non-inferential source.
    """

    model_config = {'frozen': True}

    kind: EvidenceKind
    locator: str
    excerpt: str
    retrieved_at: datetime
    extractor_version: str


class RightsRecord(BaseModel):
    """The platform's decision about whether a good may be listed, and why.

    A record is only meaningful together with its evidence. ``UNKNOWN`` is the
    default outcome for anything not provable, and it is never publishable.
    """

    candidate_id: str
    source_id: str
    license_id: str | None
    requested_actions: tuple[RightsAction, ...]
    verdict: RightsVerdict
    granted_actions: tuple[RightsAction, ...]
    obligations: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    reason: str
    engine_version: str
    decided_at: datetime
