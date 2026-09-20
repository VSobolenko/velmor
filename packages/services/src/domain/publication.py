from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from packages.services.src.domain.catalogue import CatalogueEntry


class PublicationAction(StrEnum):
    """What a publication bridge call did to the paid catalogue."""

    PUBLISHED = 'published'
    UPDATED = 'updated'
    WITHDRAWN = 'withdrawn'
    REFUSED = 'refused'
    UNCHANGED = 'unchanged'


class PublicationOutcome(BaseModel):
    """The result of one catalogue publish, update, withdraw or no-op.

    ``reasons`` is empty only for ``PUBLISHED`` and ``UPDATED``. ``entry`` is the
    catalogue row after the call when one exists; it is ``None`` only when the
    decision refused a paid entry and none was present beforehand.
    """

    model_config = {'frozen': True}

    candidate_id: str
    action: PublicationAction
    reasons: tuple[str, ...]
    entry: CatalogueEntry | None
