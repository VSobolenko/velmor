from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CatalogueCard(BaseModel):
    """One good as a buyer's card presents it.

    A deliberate projection, not a view of the stored row. ``origin_url``,
    ``content_digest`` and every storage path are absent by construction, so no
    serialiser can disclose them by accident; a test asserts the absence so a
    later field cannot quietly reintroduce one.

    ``title`` is the resolved, localised title and ``original_title`` is always
    the raw source title, kept so provenance is not hidden. ``summary`` is
    ``None`` when no presentation exists for the good or its ``ru`` fallback.

    ``size_bytes`` is ``None`` when the source never reported a size. Stating a
    size we do not have would be worse than stating that it is unknown.
    """

    model_config = {'frozen': True}

    candidate_id: str
    title: str
    original_title: str
    summary: str | None
    creator: str | None
    license_id: str | None
    obligations: tuple[str, ...]
    category_id: str | None
    category_slug: str | None
    unit_amount: str
    currency: str
    preview_url: str
    preview_is_cover: bool
    content_type: str
    size_bytes: int | None
    published_at: datetime


class CataloguePage(BaseModel):
    """One page of a catalogue query and the size of the whole answer."""

    model_config = {'frozen': True}

    items: tuple[CatalogueCard, ...]
    total: int
    limit: int
    offset: int


class CategorySummary(BaseModel):
    """A category as the shop lists it, with how many saleable goods it holds."""

    model_config = {'frozen': True}

    category_id: str
    name: str
    slug: str
    count: int


class CategoryPage(BaseModel):
    """One category's summary plus a page of its goods."""

    model_config = {'frozen': True}

    summary: CategorySummary
    items: tuple[CatalogueCard, ...]
    total: int
