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
from packages.services.src.domain.curation import (
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

    async def propose(self, candidate: Candidate) -> CurationProposal: ...


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
        '"public-domain-books") and the same category name in Russian. Use the same slug for '
        'works of the same kind so the shop has a small set of categories, not one per work.'
    )

    def __init__(self, model: str | Model) -> None:
        self._agent: Agent[None, CurationDraft] = Agent(
            model,
            output_type=CurationDraft,
            system_prompt=self.SYSTEM_PROMPT,
        )

    async def propose(self, candidate: Candidate) -> CurationProposal:
        result = await self._agent.run(self._prompt(candidate))
        draft = result.output
        return CurationProposal(
            candidate_id=candidate.id,
            copy_by_locale=(
                LocaleCopy(locale=Locale.RU, title=draft.ru_title, summary=draft.ru_summary),
                LocaleCopy(locale=Locale.BE, title=draft.be_title, summary=draft.be_summary),
                LocaleCopy(locale=Locale.EN, title=draft.en_title, summary=draft.en_summary),
            ),
            category_slug=draft.category_slug,
            category_name=draft.category_name,
        )

    @staticmethod
    def _prompt(candidate: Candidate) -> str:
        creator = candidate.creator if candidate.creator is not None else 'unknown'
        return (
            f'Source title: {candidate.title}\n'
            f'Creator: {creator}\n'
            f'Content type: {candidate.content_type}\n'
            f'Discovered at source: {candidate.source_id}\n'
        )


class CurationService:
    """Fill in the copy and the category of the goods the shop has for sale.

    A run walks the saleable catalogue and, for each good with a language it has
    no presentation for, stores what the proposer returned. It is idempotent by
    construction rather than by a deduplication step: a good stored in every
    served language is skipped, and a category is created only when its slug is
    absent, so a second run with the same proposals writes nothing at all.

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
        if not missing:
            return CurationOutcome(
                candidate_id=entry.candidate_id,
                wrote_presentation=False,
                category_slug=await self._slug_of(entry.category_id),
            )
        proposal = await self._proposer.propose(await self._require_candidate(entry))
        self._require_storable(entry, proposal)
        await self._store(entry, proposal, missing)
        return CurationOutcome(
            candidate_id=entry.candidate_id,
            wrote_presentation=True,
            category_slug=await self._assign_category(entry, proposal),
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

    async def _assign_category(
        self, entry: CatalogueEntry, proposal: CurationProposal
    ) -> str:
        category = await self._categories.by_slug(proposal.category_slug)
        if category is None:
            category = await self._category_service.create(
                name=proposal.category_name,
                slug=proposal.category_slug,
                now=self._clock(),
            )
        if entry.category_id != category.category_id:
            await self._category_service.assign(
                candidate_id=entry.candidate_id,
                category_id=category.category_id,
                product_name=self._product_name(proposal),
            )
        return category.slug

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
        if proposal.category_name.strip() == '':
            raise CurationRefusedError('curation proposed a category with no name')

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
