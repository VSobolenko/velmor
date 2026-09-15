from __future__ import annotations

import pytest

from packages.auditor.src.node_names import DECIDE, INVESTIGATE, REVIEW
from packages.auditor.src.nodes.routing import ResolutionRouter
from packages.auditor.tests.conftest import (
    ESCALATION_CONFIDENCE,
    UNCERTAIN_INTERPRETATION,
    build_state,
)
from packages.services.src.domain.interpretation import LicenseInterpretation
from packages.services.src.domain.review import HumanRuling
from packages.services.tests.conftest import build_candidate, build_spec

MAX_ATTEMPTS = 2

CONFIDENT = LicenseInterpretation(
    license_claim='MIT',
    confidence=0.9,
    quoted_text='This work is released under the MIT license.',
    reasoning='the page names the MIT license',
)
AT_THRESHOLD = LicenseInterpretation(
    license_claim='MIT',
    confidence=ESCALATION_CONFIDENCE,
    quoted_text='This work is released under the MIT license.',
    reasoning='the page names the MIT license',
)


class TestResolutionRouter:
    @pytest.mark.parametrize(
        ('resolved_license_id', 'attempts', 'expected'),
        [
            ('CC0-1.0', 0, DECIDE),
            ('CC0-1.0', MAX_ATTEMPTS, DECIDE),
            (None, 0, INVESTIGATE),
            (None, 1, INVESTIGATE),
            (None, MAX_ATTEMPTS, REVIEW),
            (None, MAX_ATTEMPTS + 3, REVIEW),
        ],
    )
    def test_every_branch(
        self,
        resolved_license_id: str | None,
        attempts: int,
        expected: str,
    ) -> None:
        router = ResolutionRouter(MAX_ATTEMPTS, ESCALATION_CONFIDENCE)
        state = build_state(
            build_candidate(license_id=None),
            build_spec(),
            resolved_license_id=resolved_license_id,
            investigation_attempts=attempts,
        )

        assert router(state) == expected

    def test_a_resolved_licence_is_never_investigated_again(self) -> None:
        router = ResolutionRouter(MAX_ATTEMPTS, ESCALATION_CONFIDENCE)
        state = build_state(
            build_candidate(license_id=None),
            build_spec(),
            resolved_license_id='MIT',
            interpretation=CONFIDENT,
            investigation_attempts=0,
        )

        assert router(state) == DECIDE

    def test_a_confident_reading_is_decided_without_a_human(self) -> None:
        router = ResolutionRouter(MAX_ATTEMPTS, ESCALATION_CONFIDENCE)
        state = build_state(
            build_candidate(license_id=None),
            build_spec(),
            resolved_license_id='MIT',
            interpretation=CONFIDENT,
        )

        assert router(state) == DECIDE

    def test_a_reading_at_the_threshold_is_decided(self) -> None:
        router = ResolutionRouter(MAX_ATTEMPTS, ESCALATION_CONFIDENCE)
        state = build_state(
            build_candidate(license_id=None),
            build_spec(),
            resolved_license_id='MIT',
            interpretation=AT_THRESHOLD,
        )

        assert router(state) == DECIDE

    def test_a_reading_below_the_threshold_is_escalated(self) -> None:
        router = ResolutionRouter(MAX_ATTEMPTS, ESCALATION_CONFIDENCE)
        state = build_state(
            build_candidate(license_id=None),
            build_spec(),
            resolved_license_id='MIT',
            interpretation=UNCERTAIN_INTERPRETATION,
        )

        assert router(state) == REVIEW

    def test_a_declared_licence_needs_no_reading_and_no_human(self) -> None:
        router = ResolutionRouter(MAX_ATTEMPTS, ESCALATION_CONFIDENCE)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            resolved_license_id='CC0-1.0',
        )

        assert router(state) == DECIDE

    def test_a_ruling_settles_an_uncertain_reading(self) -> None:
        router = ResolutionRouter(MAX_ATTEMPTS, ESCALATION_CONFIDENCE)
        state = build_state(
            build_candidate(license_id=None),
            build_spec(),
            resolved_license_id='MIT',
            interpretation=UNCERTAIN_INTERPRETATION,
            human_ruling=HumanRuling(approved=True, license_id='MIT', note='checked by hand'),
        )

        assert router(state) == DECIDE
