from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class CoverSource(StrEnum):
    """Where an attached cover came from.

    ``GENERATED`` is an image produced for the good rather than depicting it;
    the product page has to say so, which is why the source is stored and not
    merely implied by a flag. ``DOWNLOADED`` is an image we obtained, and it
    carries ``rights_note`` describing what permits us to show it.
    """

    GENERATED = 'generated'
    DOWNLOADED = 'downloaded'


class CatalogueCover(BaseModel):
    """An operator-attached image served in place of a derivative of the good.

    Used when the good itself has no usable image - a document, an archive, a
    font - so the catalogue does not present it as a broken tile. A cover is
    presentation only: it never substitutes for the good at delivery, and
    ``digest`` refers to bytes held in the asset cache, not to the origin.
    """

    model_config = {'frozen': True}

    candidate_id: str
    digest: str
    media_type: str
    source: CoverSource
    rights_note: str
    attached_at: datetime


class PreviewImage(BaseModel):
    """Bytes to serve for a good's preview, with the validator for them.

    ``from_cover`` is carried so the API can state whether the image depicts the
    good or merely represents it; the product page labels the second case.
    """

    model_config = {'frozen': True}

    payload: bytes
    media_type: str
    etag: str
    from_cover: bool
