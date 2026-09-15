from __future__ import annotations

from pydantic import BaseModel

from packages.services.src.domain.rights import RightsRecord


class GateDecision(BaseModel):
    """The publication gate's ruling, with every failed condition listed.

    ``reasons`` is never empty when ``publishable`` is false, so a rejection is
    always explainable to the person who asks why a good is missing.
    """

    model_config = {'frozen': True}

    candidate_id: str
    publishable: bool
    reasons: tuple[str, ...]
    record: RightsRecord
