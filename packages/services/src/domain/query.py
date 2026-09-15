from __future__ import annotations

from pydantic import BaseModel


class SearchQuery(BaseModel):
    """What to ask a source for.

    ``limit`` is a hard cap the connector must honour; sources paginate
    unpredictably and an uncapped query is how a crawler turns into an outage.
    """

    model_config = {'frozen': True}

    text: str
    limit: int
