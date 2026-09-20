from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Category(BaseModel):
    """One storefront category as the operator has configured it.

    ``category_id`` is Velmor's stable identity; ``saleor_category_id`` is the
    matching node in Saleor. Assignment of a good to a category stores
    ``category_id`` on the catalogue entry, so browsing never resolves the
    mapping at render time (design D4).
    """

    model_config = {'frozen': True}

    category_id: str
    name: str
    slug: str
    saleor_category_id: str
    created_at: datetime
