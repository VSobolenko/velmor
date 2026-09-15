from __future__ import annotations

from pydantic import BaseModel


class HumanRuling(BaseModel):
    """A person's ruling on a licence identity the agent could not settle.

    ``license_id`` is an identifier, not a permission: an approved ruling still
    has to resolve through the licence matrix and pass the publication gate, so a
    human can clear up *which* licence applies but cannot make a licence permit
    something it does not.
    """

    model_config = {'frozen': True}

    approved: bool
    license_id: str | None
    note: str
