from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from pydantic_ai import Agent
from pydantic_ai.models import Model

from packages.services.src.commerce.category_service import CategoryService
from packages.services.src.commerce.errors import CurationRefusedError
from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.commerce.slugs import CategorySlug
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry
from packages.services.src.domain.catalogue_query import CatalogueFilter
from packages.services.src.domain.category import Category, CategoryName
from packages.services.src.domain.curation import (
    CategoryAssignment,
    CurationDraft,
    CurationOutcome,
    CurationProposal,
    CurationRun,
    LocaleCopy,
)
from packages.services.src.domain.presentation import Locale, PresentationSource
from packages.services.src.persistence.contract import (
    CandidateRepository,
    CategoryRepository,
    StorefrontCatalog,
)


class CurationProposer(Protocol):
    """What a curation step is asked for: a proposal for one catalogued good.

    A port rather than a concrete model call, so the run can be exercised
    without a model and so a different proposer - a human, an operator's own
    text file - can be substituted without the run changing.
    """

    async def propose(
        self, candidate: Candidate, existing: tuple[Category, ...]
    ) -> CurationProposal: ...


class CatalogueCurator:
    """Propose the buyer-facing copy and the category of a good from its own record.

    The output is constrained to a schema, so a malformed or chatty answer cannot
    reach the store: either the model returns copy in every served language and a
    category, or the call fails loudly. This is the only place a model takes part
    in what a buyer reads, and it runs as an operator command; a page render
    reads stored rows and never calls it.

    The model proposes; it does not decide. Nothing it returns can make a good
    sellable, unsellable, or differently licensed - the proposal becomes a
    presentation row and a category assignment, and both are presentation.
    """

    SYSTEM_PROMPT = (
        'You write the shop copy for one digital work, from the record the platform holds. '
        'Write a display title and a one-sentence summary in Russian, Belarusian and English. '
        'The display title describes the work for a buyer; it is not the source filename, and '
        'it must not contain a file extension. Keep titles under 70 characters and summaries '
        'under 240 characters. Do not invent a creator, a date, a place or a licence: state '
        'only what the record supports. Then choose one category for the work: give a short '
        'lowercase slug of hyphen-separated words (for example "photography" or '
        '"public-domain-books") and the category name in Russian, Belarusian and English. '
        'Use the same slug for works of the same kind so the shop has a small set of '
        'categories, not one per work, and reuse an existing slug from the list of existing '
        'categories when the work belongs to it.'
    )

    def __init__(self, model: str | Model) -> None:
        self._agent: Agent[None, CurationDraft] = Agent(
            model,
            output_type=CurationDraft,
            system_prompt=self.SYSTEM_PROMPT,
        )

    async def propose(
        self, candidate: Candidate, existing: tuple[Category, ...]
    ) -> CurationProposal:
        result = await self._agent.run(self._prompt(candidate, existing))
        draft = result.output
        return CurationProposal(
            candidate_id=candidate.id,
            copy_by_locale=(
                LocaleCopy(locale=Locale.RU, title=draft.ru_title, summary=draft.ru_summary),
                LocaleCopy(locale=Locale.BE, title=draft.be_title, summary=draft.be_summary),
                LocaleCopy(locale=Locale.EN, title=draft.en_title, summary=draft.en_summary),
            ),
            category_slug=draft.category_slug,
            category_names=(
                CategoryName(locale=Locale.RU, name=draft.category_name_ru),
                CategoryName(locale=Locale.BE, name=draft.category_name_be),
                CategoryName(locale=Locale.EN, name=draft.category_name_en),
            ),
        )

    @classmethod
    def _prompt(cls, candidate: Candidate, existing: tuple[Category, ...]) -> str:
        creator = candidate.creator if candidate.creator is not None else 'unknown'
        return (
            f'Source title: {candidate.title}\n'
            f'Creator: {creator}\n'
            f'Content type: {candidate.content_type}\n'
            f'Discovered at source: {candidate.source_id}\n'
            f'{cls._existing_categories_block(existing)}\n'
        )

    @classmethod
    def _existing_categories_block(cls, existing: tuple[Category, ...]) -> str:
        """The taxonomy the model may reuse, slug and names, with no origin.

        The block carries no URL of any kind: the model is asked to place the
        work in an existing category, not to fetch where the work came from. A
        category that has no name in a served language is omitted rather than
        listed with a hole, because a partially named category is not one the
        model could reuse under a complete proposal.
        """
        lines = [
            line
            for line in (cls._existing_category_line(category) for category in existing)
            if line is not None
        ]
        if len(lines) == 0:
            lines = ['- none']
        header = 'Existing categories (reuse a slug when the work belongs to it):'
        return '\n'.join([header, *lines])

    @staticmethod
    def _existing_category_line(category: Category) -> str | None:
        names = {name.locale: name.name for name in category.names}
        if Locale.RU not in names or Locale.BE not in names or Locale.EN not in names:
            return None
        return (
            f'- {category.slug}: ru={names[Locale.RU]}; '
            f'be={names[Locale.BE]}; en={names[Locale.EN]}'
        )


class CurationService:
    """Fill in the copy and the category of the goods the shop has for sale.

    A run walks the saleable catalogue and, for each good with a language it has
    no presentation for, stores what the proposer returned. It is idempotent by
    construction rather than by a deduplication step: a good is walked past only
    when it has copy in every served language AND its own category is named in
    every served language, and a category is created only when its slug is
    absent, so a second run with the same proposals writes nothing at all. The
    second half of the condition is what lets the same pass repair a category
    created before names were localised: the good's copy is complete, so no copy
    is written, and the proposal fills the category's absent names.

    Nothing here can change what may be sold. A presentation is copy and a
    category is a label; a good the gate refused is not in the catalogue to be
    walked, and no decision, verdict or catalogue entry state is written here.
    """

    def __init__(
        self,
        catalog: StorefrontCatalog,
        candidates: CandidateRepository,
        presentations: PresentationService,
        categories: CategoryRepository,
        category_service: CategoryService,
        proposer: CurationProposer,
        clock: Callable[[], datetime],
    ) -> None:
        self._catalog = catalog
        self._candidates = candidates
        self._presentations = presentations
        self._categories = categories
        self._category_service = category_service
        self._proposer = proposer
        self._clock = clock

    async def fill_missing(self, limit: int) -> CurationRun:
        """Curate the first ``limit`` goods of the catalogue that need it."""
        matches = await self._catalog.search(
            CatalogueFilter(category_id=None, license_id=None)
        )
        outcomes: list[CurationOutcome] = []
        for entry in matches.entries[:limit]:
            outcomes.append(await self._curate(entry))
        return CurationRun(outcomes=tuple(outcomes))

    async def _curate(self, entry: CatalogueEntry) -> CurationOutcome:
        missing = await self._presentations.missing_locales(entry.candidate_id)
        if not missing and await self._category_is_fully_named(entry.category_id):
            return CurationOutcome(
                candidate_id=entry.candidate_id,
                wrote_presentation=False,
                filled_category_names=False,
                category_slug=await self._slug_of(entry.category_id),
                created_category=False,
            )
        # Read the taxonomy per proposal, not once per run: fill_missing creates
        # categories as it loops, so a snapshot taken before the first good is
        # stale by the second and a pass would create duplicates of its own work.
        existing = await self._categories.all()
        proposal = await self._proposer.propose(
            await self._require_candidate(entry), existing
        )
        self._require_storable(entry, proposal)
        await self._store(entry, proposal, missing)
        assignment = await self._assign_category(entry, proposal)
        return CurationOutcome(
            candidate_id=entry.candidate_id,
            wrote_presentation=len(missing) > 0,
            filled_category_names=assignment.filled_names,
            category_slug=assignment.slug,
            created_category=assignment.created_category,
        )

    async def _store(
        self,
        entry: CatalogueEntry,
        proposal: CurationProposal,
        missing: tuple[Locale, ...],
    ) -> None:
        for copy in proposal.copy_by_locale:
            if copy.locale not in missing:
                continue
            await self._presentations.record(
                candidate_id=entry.candidate_id,
                locale=copy.locale,
                title=copy.title,
                summary=copy.summary,
                source=PresentationSource.MODEL,
                now=self._clock(),
            )

    async def _category_is_fully_named(self, category_id: str | None) -> bool:
        """Whether this good's own category already has a name in every served language.

        A good with no category needs no name repair, and neither does a
        ``category_id`` that resolves to no stored category: a dangling
        reference is not something a repair pass may fail on. This reads the
        good's own category rather than the per-proposal taxonomy, because the
        decision to walk past a good is made before a proposal exists.
        """
        if category_id is None:
            return True
        category = await self._categories.by_id(category_id)
        if category is None:
            return True
        named = {name.locale for name in category.names}
        return all(locale in named for locale in Locale)

    async def _assign_category(
        self, entry: CatalogueEntry, proposal: CurationProposal
    ) -> CategoryAssignment:
        """Assign the good, creating the category only when its slug is absent.

        An existing category keeps the names it already has: the proposal fills
        only the served languages the category is missing, and a create writes
        them all. Nothing else on an existing category changes, so a repair pass
        cannot rename a category or reach the external catalogue with it. The
        return reports creating, filling and reusing separately, because a
        reused category that gained a name is not a created category.
        """
        category = await self._categories.by_slug(proposal.category_slug)
        created_category = False
        filled_names = False
        if category is None:
            category = await self._category_service.create(
                name=self._category_name(proposal),
                slug=proposal.category_slug,
                names=proposal.category_names,
                now=self._clock(),
            )
            created_category = True
            filled_names = True
        else:
            merged = self._merged_category_names(category.names, proposal.category_names)
            if merged != category.names:
                category = category.model_copy(update={'names': merged})
                await self._categories.save_category(category)
                filled_names = True
        if entry.category_id != category.category_id:
            await self._category_service.assign(
                candidate_id=entry.candidate_id,
                category_id=category.category_id,
                product_name=self._product_name(proposal),
            )
        return CategoryAssignment(
            slug=category.slug,
            created_category=created_category,
            filled_names=filled_names,
        )

    @staticmethod
    def _merged_category_names(
        stored: tuple[CategoryName, ...], proposed: tuple[CategoryName, ...]
    ) -> tuple[CategoryName, ...]:
        """Every served language once, a stored name winning over a proposed one.

        Ordered by ``Locale`` rather than by the order the proposal listed, so
        the merged tuple is the same on any machine. A stored name is written
        last and therefore kept, which is what makes a repair fill a gap without
        overwriting an operator's copy.
        """
        by_locale = {name.locale: name for name in proposed}
        for name in stored:
            by_locale[name.locale] = name
        return tuple(by_locale[locale] for locale in Locale)

    async def _require_candidate(self, entry: CatalogueEntry) -> Candidate:
        candidate = await self._candidates.by_candidate_id(entry.candidate_id)
        if candidate is None:
            raise CurationRefusedError(
                f'catalogue entry {entry.candidate_id} has no candidate row to curate from'
            )
        return candidate

    @staticmethod
    def _require_storable(entry: CatalogueEntry, proposal: CurationProposal) -> None:
        """Refuse a proposal that would store copy no page could show.

        A row with an empty title renders a blank card and a slug that is not a
        slug produces a category no address can reach, so both are refused at the
        point they would be written rather than stored and discovered later. The
        proposal is also required to answer for the good it was asked about: a
        proposer that returns another good's id would otherwise write copy onto
        the wrong row.
        """
        if proposal.candidate_id != entry.candidate_id:
            raise CurationRefusedError(
                f'curation proposed for {proposal.candidate_id!r} while curating '
                f'{entry.candidate_id!r}'
            )
        if tuple(copy.locale for copy in proposal.copy_by_locale) != tuple(Locale):
            raise CurationRefusedError(
                f'curation proposed copy for '
                f'{[copy.locale.value for copy in proposal.copy_by_locale]} '
                f'rather than every served language'
            )
        for copy in proposal.copy_by_locale:
            if copy.title.strip() == '' or copy.summary.strip() == '':
                raise CurationRefusedError(
                    f'curation proposed an empty {copy.locale.value} title or summary'
                )
        if not CategorySlug.is_valid(proposal.category_slug):
            raise CurationRefusedError(
                f'curation proposed {proposal.category_slug!r}, which is not a category slug'
            )
        CurationService._require_category_names(proposal)

    @staticmethod
    def _require_category_names(proposal: CurationProposal) -> None:
        """Refuse a category name set that does not cover every served language.

        The reason names the absent language, so an operator reading the failure
        knows which field to fix rather than which proposal to re-read. An empty
        name is refused for the same reason: it renders as a blank label a buyer
        cannot act on.
        """
        proposed = {name.locale for name in proposal.category_names}
        absent = tuple(locale for locale in Locale if locale not in proposed)
        if len(absent) > 0:
            raise CurationRefusedError(
                f'curation proposed no category name for '
                f'{[locale.value for locale in absent]}'
            )
        for name in proposal.category_names:
            if name.name.strip() == '':
                raise CurationRefusedError(
                    f'curation proposed an empty {name.locale.value} category name'
                )

    async def _slug_of(self, category_id: str | None) -> str | None:
        if category_id is None:
            return None
        category = await self._categories.by_id(category_id)
        if category is None:
            return None
        return category.slug

    @staticmethod
    def _product_name(proposal: CurationProposal) -> str:
        for copy in proposal.copy_by_locale:
            if copy.locale is Locale.RU:
                return copy.title
        raise CurationRefusedError(
            f'curation proposed no {Locale.RU.value} title to name the product with'
        )

    @staticmethod
    def _category_name(proposal: CurationProposal) -> str:
        """The one name the external catalogue node receives: the Russian one.

        Saleor is the external catalogue, not what the storefront reads to show a
        name, and a category node has exactly one name. The same rule
        ``_product_name`` already applies to a product's name.
        """
        for name in proposal.category_names:
            if name.locale is Locale.RU:
                return name.name
        raise CurationRefusedError(
            f'curation proposed no {Locale.RU.value} category name to name the category with'
        )
