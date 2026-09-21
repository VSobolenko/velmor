from __future__ import annotations

from pydantic import BaseModel

from packages.services.src.domain.presentation import Locale


class LocaleCopy(BaseModel):
    """Buyer-facing copy for one good in one language, as a curation step proposed it."""

    model_config = {'frozen': True}

    locale: Locale
    title: str
    summary: str


class CurationDraft(BaseModel):
    """What the curation model is asked to return, as a schema it must satisfy.

    One field per language rather than a list, so an omitted language is a
    validation failure of the model's own output type instead of a gap discovered
    afterwards. ``category_name`` is in Russian because a category's stored name
    is one string for the whole shop, and Russian is the shop's default language.
    """

    model_config = {'frozen': True}

    ru_title: str
    ru_summary: str
    be_title: str
    be_summary: str
    en_title: str
    en_summary: str
    category_slug: str
    category_name: str


class CurationProposal(BaseModel):
    """A curator's proposal for one catalogued good.

    ``copy_by_locale`` is named for the languages it answers in rather than
    ``copy``, which a ``BaseModel`` already defines as a method. ``category_slug``
    is the identity of the category the good belongs in and ``category_name`` is
    how that category is displayed; the slug is what decides whether the category
    has to be created, so two runs proposing the same slug cannot produce two
    categories.
    """

    model_config = {'frozen': True}

    candidate_id: str
    copy_by_locale: tuple[LocaleCopy, ...]
    category_slug: str
    category_name: str


class CurationOutcome(BaseModel):
    """What one curation run did to one good.

    ``wrote_presentation`` is false for a good that already had copy in every
    served language, which is the whole of idempotence: the run reports the good
    it walked past as clearly as the good it wrote.
    """

    model_config = {'frozen': True}

    candidate_id: str
    wrote_presentation: bool
    category_slug: str | None


class CurationRun(BaseModel):
    """One curation run, in the order it walked the catalogue."""

    model_config = {'frozen': True}

    outcomes: tuple[CurationOutcome, ...]
