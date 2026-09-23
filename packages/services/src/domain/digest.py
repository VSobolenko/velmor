from __future__ import annotations

from pydantic import BaseModel


class DigestResult(BaseModel):
    """Outcome of hashing an origin payload at publication time.

    ``renderable`` records whether the same bytes can become a preview. It is a
    plain field with no behaviour: the decision is made where the bytes are, in
    ``ImagePayload``, and publication reads the answer rather than repeating the
    check.
    """

    model_config = {'frozen': True}

    digest: str
    size_bytes: int
    cached: bool
    renderable: bool
