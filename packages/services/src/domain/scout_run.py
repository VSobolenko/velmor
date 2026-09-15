from __future__ import annotations

from pydantic import BaseModel


class SourceFailure(BaseModel):
    """One source that failed during a run, and why.

    A failing source never fails the run: discovery is best-effort across sources
    and the failure is reported so it can be seen instead of silently shrinking
    the funnel.
    """

    model_config = {'frozen': True}

    source_id: str
    reason: str


class ScoutRun(BaseModel):
    """Outcome of one discovery pass."""

    model_config = {'frozen': True}

    run_id: str
    query: str
    sources_queried: tuple[str, ...]
    discovered: int
    persisted: int
    failures: tuple[SourceFailure, ...]
