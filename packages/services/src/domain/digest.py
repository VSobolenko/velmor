from __future__ import annotations

from pydantic import BaseModel


class DigestResult(BaseModel):
    """Outcome of hashing an origin payload at publication time."""

    model_config = {'frozen': True}

    digest: str
    size_bytes: int
    cached: bool
