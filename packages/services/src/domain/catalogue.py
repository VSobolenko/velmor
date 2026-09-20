from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from packages.services.src.domain.license import StorefrontListing


class CatalogueEntryState(StrEnum):
    """Whether a catalogue entry is on sale or has been withdrawn.

    An explicit state rather than a nullable withdrawal timestamp whose presence
    means withdrawn: the entry is compared against a value, never tested for
    truthiness, and the state is what a storefront report counts.
    """

    PUBLISHED = 'published'
    WITHDRAWN = 'withdrawn'


class CatalogueEntry(BaseModel):
    """One publishable good as it exists in the paid catalogue.

    ``candidate_id`` is the internal link back to the ``RightsRecord`` and
    ``GateDecision`` that justified the entry, which are keyed by it. The
    licence identity and the obligations of that record are captured here at
    publication so the download page can state them without reading a later
    record, and ``listing`` is the ``StorefrontListing`` the decision held, which
    the checkout consults before it prices the good.

    ``category_id``, ``license_id`` and ``withdrawal_reason`` are optional
    because each is absent until the operation that sets it runs: a good may be
    published before it is categorised, a record may carry no resolved licence
    identity, and an entry that was never withdrawn has no reason to report.
    """

    model_config = {'frozen': True}

    candidate_id: str
    source_id: str
    saleor_product_id: str
    saleor_variant_id: str
    category_id: str | None = None
    license_id: str | None = None
    obligations: tuple[str, ...]
    listing: StorefrontListing
    state: CatalogueEntryState
    withdrawal_reason: str | None = None
    published_at: datetime
