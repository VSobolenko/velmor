from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from packages.services.src.domain.presentation import Locale


class CategoryName(BaseModel):
    """A buyer-facing category name in one served language.

    One row per locale rather than a map or nullable columns, so resolving a
    language is a lookup and a fallback and never a truthiness test over a
    mostly-empty record. A language is never chosen for the buyer: a name is
    data, and a surface reads the one stored for the language being read.
    """

    model_config = {'frozen': True}

    locale: Locale
    name: str


class Category(BaseModel):
    """One storefront category as the operator has configured it.

    ``category_id`` is Velmor's stable identity; ``saleor_category_id`` is the
    matching node in Saleor. Assignment of a good to a category stores
    ``category_id`` on the catalogue entry, so browsing never resolves the
    mapping at render time (design D4).

    ``name`` is the operator-facing and external-catalogue label. A Saleor
    category node has exactly one name, ``CategoryRepository.all`` orders by it,
    and it exists so neither ordering nor the external catalogue depends on the
    language a buyer reads. It is NOT what a buyer reads: a buyer-facing name is
    resolved for a language from ``names``, and the scalar is never returned by
    that resolution.
    """

    model_config = {'frozen': True}

    category_id: str
    name: str
    slug: str
    saleor_category_id: str
    created_at: datetime
    names: tuple[CategoryName, ...]
