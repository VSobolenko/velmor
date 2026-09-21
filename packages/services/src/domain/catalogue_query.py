from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from packages.services.src.domain.catalogue import CatalogueEntry


class CatalogueSort(StrEnum):
    """The orders a catalogue query may ask for.

    A closed set because an unrecognised value must be refused at the request
    edge, not silently treated as the default: a buyer who asked for
    ``price_asc`` and received an arbitrary order has been told something false
    about the shop.
    """

    NEWEST = 'newest'
    PRICE_ASC = 'price_asc'
    PRICE_DESC = 'price_desc'
    TITLE_ASC = 'title_asc'
    TITLE_DESC = 'title_desc'


class CatalogueFilter(BaseModel):
    """The part of a query a store can apply without resolving a locale.

    ``category_id`` is Velmor's category identity, not the slug a buyer sees;
    the service resolves the slug before it builds this. The text term is
    deliberately absent: it matches the title resolved for a locale, which only
    the service knows, so pushing it into the store would match a different set
    of goods than the one the buyer is shown.
    """

    model_config = {'frozen': True}

    category_id: str | None
    license_id: str | None


class CatalogueMatches(BaseModel):
    """Catalogued goods matching the pushable filters, and how many there are.

    ``total`` is the count of every match, not the size of a page, so a caller
    that reports it is stating the size of the catalogue's answer rather than
    the cap it happened to request.
    """

    model_config = {'frozen': True}

    entries: tuple[CatalogueEntry, ...]
    total: int


class CategoryGoodsCount(BaseModel):
    """How many saleable goods one category holds."""

    model_config = {'frozen': True}

    category_id: str
    count: int
