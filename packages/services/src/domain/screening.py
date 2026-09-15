from __future__ import annotations

from pydantic import BaseModel


class ScreeningResult(BaseModel):
    """Outcome of a category screen over one candidate."""

    model_config = {'frozen': True}

    candidate_id: str
    clear: bool
    violations: tuple[str, ...]
