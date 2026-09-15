from __future__ import annotations

from pydantic import BaseModel


class Candidate(BaseModel):
    """A single good discovered at a source, before any rights decision.

    Mutable on purpose: agent nodes enrich it in place as they gather evidence.
    """

    id: str
    source_id: str
    title: str
    landing_url: str
    creator: str | None
    content_type: str
    declared_license_id: str | None
    declared_license_text: str | None
    download_url: str | None
    size_bytes: int | None
