from __future__ import annotations

from datetime import UTC, datetime

from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.domain.presentation import (
    CataloguePresentation,
    Locale,
    PresentationSource,
)
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate

UPDATED_AT = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
CANDIDATE_ID = 'openverse:1'


def build_presentation(
    locale: Locale = Locale.RU,
    title: str = 'Curated title',
    summary: str = 'Curated summary',
    candidate_id: str = CANDIDATE_ID,
    source: PresentationSource = PresentationSource.OPERATOR,
) -> CataloguePresentation:
    return CataloguePresentation(
        candidate_id=candidate_id,
        locale=locale,
        title=title,
        summary=summary,
        source=source,
        updated_at=UPDATED_AT,
    )


class TestPresentationResolution:
    async def test_the_requested_locale_wins(self) -> None:
        store = InMemoryStore()
        await store.save_presentation(build_presentation(Locale.RU, title='Русский'))
        await store.save_presentation(build_presentation(Locale.EN, title='English'))
        service = PresentationService(store)

        resolved = await service.resolve(build_candidate(), Locale.EN)

        assert resolved.title == 'English'
        assert resolved.is_fallback_title is False

    async def test_an_absent_locale_falls_back_to_russian(self) -> None:
        store = InMemoryStore()
        await store.save_presentation(build_presentation(Locale.RU, title='Русский'))
        service = PresentationService(store)

        resolved = await service.resolve(build_candidate(), Locale.BE)

        assert resolved.title == 'Русский'
        assert resolved.summary == 'Curated summary'
        assert resolved.is_fallback_title is False

    async def test_no_presentation_falls_back_to_the_shortened_source_title(self) -> None:
        store = InMemoryStore()
        service = PresentationService(store)

        resolved = await service.resolve(build_candidate(title='A filename.jpg'), Locale.RU)

        assert resolved.title == 'A filename.jpg'
        assert resolved.summary is None
        assert resolved.is_fallback_title is True

    async def test_the_original_title_is_always_the_source_title(self) -> None:
        store = InMemoryStore()
        await store.save_presentation(build_presentation(title='Curated'))
        service = PresentationService(store)

        resolved = await service.resolve(build_candidate(title='raw_source.png'), Locale.RU)

        assert resolved.title == 'Curated'
        assert resolved.original_title == 'raw_source.png'

    async def test_resolving_many_answers_for_each_good(self) -> None:
        store = InMemoryStore()
        await store.save_presentation(build_presentation(Locale.EN, title='English'))
        service = PresentationService(store)
        first = build_candidate(candidate_id=CANDIDATE_ID, title='raw.png')
        second = build_candidate(candidate_id='openverse:2', title='other.png')

        resolved = await service.resolve_many((first, second), Locale.EN)

        assert tuple(item.title for item in resolved) == ('English', 'other.png')
        assert tuple(item.is_fallback_title for item in resolved) == (False, True)


class TestMissingLocales:
    async def test_every_served_language_is_missing_before_curation(self) -> None:
        service = PresentationService(InMemoryStore())

        assert await service.missing_locales(CANDIDATE_ID) == tuple(Locale)

    async def test_only_the_absent_languages_are_reported(self) -> None:
        store = InMemoryStore()
        await store.save_presentation(build_presentation(Locale.RU))
        service = PresentationService(store)

        assert await service.missing_locales(CANDIDATE_ID) == (Locale.BE, Locale.EN)

    async def test_a_language_stored_twice_is_not_reported_missing(self) -> None:
        store = InMemoryStore()
        for locale in Locale:
            await store.save_presentation(build_presentation(locale))
        service = PresentationService(store)

        assert await service.missing_locales(CANDIDATE_ID) == ()


class TestRecording:
    async def test_a_stored_record_names_who_wrote_it(self) -> None:
        store = InMemoryStore()
        service = PresentationService(store)

        recorded = await service.record(
            candidate_id=CANDIDATE_ID,
            locale=Locale.EN,
            title='Title',
            summary='Summary',
            source=PresentationSource.MODEL,
            now=UPDATED_AT,
        )

        assert recorded.source is PresentationSource.MODEL
        assert await store.presentations_for(CANDIDATE_ID) == (recorded,)

    async def test_recording_the_same_locale_replaces_the_row(self) -> None:
        store = InMemoryStore()
        service = PresentationService(store)
        await service.record(
            CANDIDATE_ID, Locale.RU, 'First', 'Summary', PresentationSource.OPERATOR, UPDATED_AT
        )

        await service.record(
            CANDIDATE_ID, Locale.RU, 'Second', 'Summary', PresentationSource.OPERATOR, UPDATED_AT
        )

        stored = await store.presentations_for(CANDIDATE_ID)
        assert len(stored) == 1
        assert stored[0].title == 'Second'


class TestSourceTitleShortening:
    def test_a_short_title_is_collapsed_but_kept_whole(self) -> None:
        assert PresentationService.shorten_source_title('  A   short  name.png ') == (
            'A short name.png'
        )

    def test_a_long_title_is_clipped_on_a_word_boundary(self) -> None:
        title = ' '.join(['word'] * 40)

        shortened = PresentationService.shorten_source_title(title)

        assert len(shortened) <= PresentationService.SOURCE_TITLE_MAX_CHARS + 1
        assert shortened.endswith(PresentationService.ELLIPSIS)
        assert 'word' in shortened

    def test_a_single_unbroken_run_is_clipped_without_a_boundary(self) -> None:
        shortened = PresentationService.shorten_source_title('x' * 200)

        assert shortened == f'{"x" * PresentationService.SOURCE_TITLE_MAX_CHARS}…'
