from __future__ import annotations

import pytest

from packages.services.src.domain.candidate import Candidate
from packages.services.src.screening.prohibited_screen import ProhibitedCategoryScreen
from packages.services.tests.conftest import build_candidate


@pytest.fixture
def screen() -> ProhibitedCategoryScreen:
    return ProhibitedCategoryScreen()


def build_titled_candidate(title: str, content_type: str = 'image') -> Candidate:
    return Candidate(
        id='x:1',
        source_id='x',
        title=title,
        landing_url='https://example.test',
        creator=None,
        content_type=content_type,
        declared_license_id='MIT',
        declared_license_text=None,
        download_url=None,
        size_bytes=None,
    )


class TestProhibitedCategoryScreen:
    def test_a_plain_licensed_work_passes(self, screen: ProhibitedCategoryScreen) -> None:
        result = screen.screen(build_candidate('MIT'))

        assert result.clear is True
        assert result.violations == ()

    @pytest.mark.parametrize(
        'title',
        [
            'Cheap Windows license key',
            'Premium account access',
            'Cracked photo editor',
            'Steam key bundle',
        ],
    )
    def test_prohibited_categories_are_caught_regardless_of_license(
        self, screen: ProhibitedCategoryScreen, title: str
    ) -> None:
        result = screen.screen(build_titled_candidate(title))

        assert result.clear is False
        assert result.violations

    def test_screening_does_not_depend_on_the_declared_license(
        self, screen: ProhibitedCategoryScreen
    ) -> None:
        permissive_key = build_titled_candidate('Original software activation key bundle')

        assert permissive_key.declared_license_id == 'MIT'
        assert screen.screen(permissive_key).clear is False

    def test_every_violation_is_reported(self, screen: ProhibitedCategoryScreen) -> None:
        result = screen.screen(build_titled_candidate('Cracked app with license key included'))

        assert len(result.violations) >= 2

    def test_result_carries_the_candidate_id(self, screen: ProhibitedCategoryScreen) -> None:
        result = screen.screen(build_candidate('MIT'))

        assert result.candidate_id == 'openverse:1'
