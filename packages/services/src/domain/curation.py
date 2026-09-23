from __future__ import annotations

from pydantic import BaseModel

from packages.services.src.domain.category import CategoryName
from packages.services.src.domain.presentation import Locale


class LocaleCopy(BaseModel):
    """Buyer-facing copy for one good in one language, as a curation step proposed it."""

    model_config = {'frozen': True}

    locale: Locale
    title: str
    summary: str


class CurationDraft(BaseModel):
    """What the curation model is asked to return, as a schema it must satisfy.

    One field per language rather than a list, for the copy and for the category
    name alike, so an omitted language is a validation failure of the model's own
    output type instead of a gap discovered afterwards. The previous single
    ``category_name`` was justified by a category having one stored name for the
    whole shop; that is no longer true, because a category's name is buyer-facing
    per language, so the field is one per served language.
    """

    model_config = {'frozen': True}

    ru_title: str
    ru_summary: str
    be_title: str
    be_summary: str
    en_title: str
    en_summary: str
    category_slug: str
    category_name_ru: str
    category_name_be: str
    category_name_en: str


class CurationProposal(BaseModel):
    """A curator's proposal for one catalogued good.

    ``copy_by_locale`` is named for the languages it answers in rather than
    ``copy``, which a ``BaseModel`` already defines as a method. ``category_slug``
    is the identity of the category the good belongs in and ``category_names``
    carries the buyer-facing name for every served language; the slug is what
    decides whether the category has to be created, so two runs proposing the
    same slug cannot produce two categories.
    """

    model_config = {'frozen': True}

    candidate_id: str
    copy_by_locale: tuple[LocaleCopy, ...]
    category_slug: str
    category_names: tuple[CategoryName, ...]


class CategoryAssignment(BaseModel):
    """What assigning a good to a category did, for the run outcome to report.

    Three facts travel together and mean different things, so they are one named
    object rather than a bare tuple a reader has to unpack by position: a reused
    category that gained a name is not a created category, and a create writes
    every name by definition.
    """

    model_config = {'frozen': True}

    slug: str
    created_category: bool
    filled_names: bool


class CurationOutcome(BaseModel):
    """What one curation run did to one good.

    ``wrote_presentation`` is true only when this outcome stored copy; it is
    false for a good whose copy was already complete, and false too for a repair
    pass that only named a category, because a repair writes no copy.
    ``filled_category_names`` is the separate fact that a name was written onto
    a category missing one, so a repair-only run does not read as a run that did
    nothing. ``created_category`` is true only when this outcome created the
    category; it is false when the category already existed, and false too when
    nothing was written, so the report can state that an existing category was
    reused.
    """

    model_config = {'frozen': True}

    candidate_id: str
    wrote_presentation: bool
    filled_category_names: bool
    category_slug: str | None
    created_category: bool


class CurationRun(BaseModel):
    """One curation run, in the order it walked the catalogue."""

    model_config = {'frozen': True}

    outcomes: tuple[CurationOutcome, ...]
