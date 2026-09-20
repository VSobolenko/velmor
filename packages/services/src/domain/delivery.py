from __future__ import annotations

from pydantic import BaseModel


class DeliveryResult(BaseModel):
    """Bytes and attribution returned to an entitled buyer.

    Deliberately carries no origin locator: the buyer must never learn where the
    file was fetched from.
    """

    model_config = {'frozen': True}

    candidate_id: str
    payload: bytes
    content_digest: str
    license_id: str | None
    obligations: tuple[str, ...]
