from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LicenseInterpretation(BaseModel):
    """A structured reading of whatever rights statement a page contains.

    The model's job is extraction, not judgement. It reports what the page claims
    and how sure it is; whether that claim is enough to sell something is decided
    afterwards by the license matrix and the publication gate, neither of which
    trusts this object on its own.
    """

    model_config = {'frozen': True}

    license_claim: str | None
    confidence: float
    quoted_text: str
    reasoning: str


class InterpretationRecord(BaseModel):
    """An interpretation together with where it came from, for the audit trail."""

    model_config = {'frozen': True}

    source_url: str
    model_name: str
    interpretation: LicenseInterpretation
    created_at: datetime
