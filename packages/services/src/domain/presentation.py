from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class Locale(StrEnum):
    """The locales the shop serves.

    A closed set, not a free string: a store and a service cannot disagree about
    which locale codes exist, an unknown one is refused at the edge by request
    validation instead of quietly falling back, and presentation rows are keyed
    by it. The order here is the order of the language switcher's fallback list,
    not a preference.
    """

    RU = 'ru'
    BE = 'be'
    EN = 'en'


DEFAULT_LOCALE: Locale = Locale.RU


class PresentationSource(StrEnum):
    """Who produced a presentation record.

    Recorded so a reviewer can tell copy a model proposed from copy a human
    wrote, which is the difference between a suggestion and a decision.
    """

    MODEL = 'model'
    OPERATOR = 'operator'


class CataloguePresentation(BaseModel):
    """Buyer-facing copy for one catalogued good in one locale.

    One row per locale rather than nullable columns on a single row, so
    resolving a locale is a lookup and a fallback, never a truthiness test over
    a mostly-empty record. ``candidate_id`` is the only link to the catalogue:
    a presentation carries no price, no licence and no eligibility, so it cannot
    become a second opinion about what may be sold.
    """

    model_config = {'frozen': True}

    candidate_id: str
    locale: Locale
    title: str
    summary: str
    source: PresentationSource
    updated_at: datetime


class ResolvedPresentation(BaseModel):
    """What a buyer actually reads for one good, after fallback.

    ``is_fallback_title`` is reported rather than inferred by the caller so a
    page can tell curated copy from a source filename without re-deriving the
    rule, and so a test can assert which branch produced the title.
    """

    model_config = {'frozen': True}

    candidate_id: str
    title: str
    original_title: str
    summary: str | None
    is_fallback_title: bool
