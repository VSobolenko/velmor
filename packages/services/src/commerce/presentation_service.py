from __future__ import annotations

from datetime import datetime

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.presentation import (
    DEFAULT_LOCALE,
    CataloguePresentation,
    Locale,
    PresentationSource,
    ResolvedPresentation,
)
from packages.services.src.persistence.contract import CataloguePresentationRepository


class PresentationService:
    """Resolve the copy a buyer reads for a good, and record what curation stored.

    The resolution is a lookup and a fallback over stored rows, in the order the
    contract fixes: the requested locale, then ``ru``, then a shortened source
    title. Nothing here calls a model, reads a clock or touches the network, so
    a page render cannot resolve a language by inference and cannot change what
    may be sold.

    ``is_fallback_title`` is reported rather than left for the caller to derive,
    so a page can tell curated copy from a source filename and a test can assert
    which branch produced the title.
    """

    SOURCE_TITLE_MAX_CHARS = 80
    ELLIPSIS = '\u2026'

    def __init__(self, presentations: CataloguePresentationRepository) -> None:
        self._presentations = presentations

    async def resolve(self, candidate: Candidate, locale: Locale) -> ResolvedPresentation:
        stored = await self._presentations.presentations_for(candidate.id)
        return self._resolve_from(candidate, locale, stored)

    async def resolve_many(
        self, candidates: tuple[Candidate, ...], locale: Locale
    ) -> tuple[ResolvedPresentation, ...]:
        """Resolve many goods from one read of the presentation table.

        The catalogue resolves a title for every match it considered, so a read
        per good would turn one page into a query per catalogue entry.
        """
        stored = await self._presentations.all_presentations()
        by_candidate: dict[str, list[CataloguePresentation]] = {}
        for presentation in stored:
            if presentation.candidate_id not in by_candidate:
                by_candidate[presentation.candidate_id] = []
            by_candidate[presentation.candidate_id].append(presentation)
        resolved: list[ResolvedPresentation] = []
        for candidate in candidates:
            rows = by_candidate.get(candidate.id)
            if rows is None:
                resolved.append(self._resolve_from(candidate, locale, ()))
            else:
                resolved.append(self._resolve_from(candidate, locale, tuple(rows)))
        return tuple(resolved)

    async def record(
        self,
        candidate_id: str,
        locale: Locale,
        title: str,
        summary: str,
        source: PresentationSource,
        now: datetime,
    ) -> CataloguePresentation:
        presentation = CataloguePresentation(
            candidate_id=candidate_id,
            locale=locale,
            title=title,
            summary=summary,
            source=source,
            updated_at=now,
        )
        await self._presentations.save_presentation(presentation)
        return presentation

    async def missing_locales(self, candidate_id: str) -> tuple[Locale, ...]:
        """The served languages this good has no stored presentation for.

        Reported as a set of languages rather than as a yes/no "is curated", so a
        run fills the gap that exists instead of rewriting copy an operator has
        already edited: a good with Russian only gets Belarusian and English, and
        its Russian row is left alone.
        """
        stored = await self._presentations.presentations_for(candidate_id)
        present = {presentation.locale for presentation in stored}
        return tuple(locale for locale in Locale if locale not in present)

    @classmethod
    def shorten_source_title(cls, title: str) -> str:
        """A source filename trimmed to something a card can carry.

        Curation is what makes a good presentable; until it has run, the raw
        source title is all there is, and the alternative - showing a buyer a
        150-character filename - is the failure this change exists to fix.
        """
        collapsed = ' '.join(title.split())
        if len(collapsed) <= cls.SOURCE_TITLE_MAX_CHARS:
            return collapsed
        clipped = collapsed[: cls.SOURCE_TITLE_MAX_CHARS].rstrip()
        if ' ' in clipped:
            stem = clipped[: clipped.rindex(' ')]
        else:
            stem = clipped
        return f'{stem}{cls.ELLIPSIS}'

    def _resolve_from(
        self,
        candidate: Candidate,
        locale: Locale,
        stored: tuple[CataloguePresentation, ...],
    ) -> ResolvedPresentation:
        requested = self._locale_row(stored, locale)
        if requested is not None:
            return self._from_row(candidate, requested, is_fallback_title=False)
        fallback = self._locale_row(stored, DEFAULT_LOCALE)
        if fallback is not None:
            return self._from_row(candidate, fallback, is_fallback_title=False)
        return ResolvedPresentation(
            candidate_id=candidate.id,
            title=self.shorten_source_title(candidate.title),
            original_title=candidate.title,
            summary=None,
            is_fallback_title=True,
        )

    @staticmethod
    def _locale_row(
        stored: tuple[CataloguePresentation, ...], locale: Locale
    ) -> CataloguePresentation | None:
        for presentation in stored:
            if presentation.locale is locale:
                return presentation
        return None

    @staticmethod
    def _from_row(
        candidate: Candidate,
        presentation: CataloguePresentation,
        is_fallback_title: bool,
    ) -> ResolvedPresentation:
        return ResolvedPresentation(
            candidate_id=candidate.id,
            title=presentation.title,
            original_title=candidate.title,
            summary=presentation.summary,
            is_fallback_title=is_fallback_title,
        )
