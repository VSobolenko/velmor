from __future__ import annotations

import pytest

from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.verification_run import (
    CandidateOutcome,
    CategoryRefusal,
    VerificationOutcome,
    VerificationRun,
)
from packages.services.tests.conftest import build_record
from velmor.agents.auditor import AuditorRunReport


def build_outcome(
    candidate_id: str,
    outcome: VerificationOutcome,
    reasons: tuple[str, ...],
    decided: bool,
) -> CandidateOutcome:
    if not decided:
        return CandidateOutcome(
            candidate_id=candidate_id,
            outcome=outcome,
            reasons=reasons,
            decision=None,
        )
    return CandidateOutcome(
        candidate_id=candidate_id,
        outcome=outcome,
        reasons=reasons,
        decision=GateDecision(
            candidate_id=candidate_id,
            publishable=outcome is VerificationOutcome.PUBLISHED,
            reasons=reasons,
            record=build_record(),
        ),
    )


def build_run() -> VerificationRun:
    return VerificationRun(
        run_id='run-1',
        outcomes=(
            build_outcome('openverse:1', VerificationOutcome.PUBLISHED, (), decided=True),
            build_outcome(
                'openverse:2',
                VerificationOutcome.REFUSED,
                ('Rights verdict is denied: CC-BY-NC-4.0 does not grant: resell',),
                decided=True,
            ),
            build_outcome(
                'openverse:3',
                VerificationOutcome.SCREENED_OUT,
                ('Prohibited category matched: crack',),
                decided=False,
            ),
            build_outcome(
                'openverse:4',
                VerificationOutcome.PAUSED,
                ('Awaiting human review: no publication decision yet',),
                decided=False,
            ),
        ),
        refusals_by_category=(CategoryRefusal(category='crack', count=1),),
    )


class TestAuditorRunReport:
    def test_every_outcome_is_counted_under_its_own_label(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        AuditorRunReport().show(build_run())

        out = capsys.readouterr().out

        assert 'candidates=4' in out
        assert 'PUBLISH=1' in out
        assert 'REJECT=1' in out
        assert 'SCREENED OUT=1' in out
        assert 'PAUSED=1' in out

    def test_a_paused_candidate_is_reported_as_paused_not_as_a_refusal(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        AuditorRunReport().show(build_run())

        lines = capsys.readouterr().out.splitlines()
        paused = [line for line in lines if 'openverse:4' in line]

        assert len(paused) == 1
        assert 'PAUSED' in paused[0]
        assert 'REJECT' not in paused[0]

    def test_a_screened_out_candidate_names_the_category(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        AuditorRunReport().show(build_run())

        out = capsys.readouterr().out

        assert "screened 'crack': 1" in out
        assert 'SCREENED OUT openverse:3' in out

    def test_a_published_candidate_says_why_it_passed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        AuditorRunReport().show(build_run())

        out = capsys.readouterr().out

        assert 'PUBLISH openverse:1 [CC-BY-4.0] all conditions met' in out

    def test_a_refusal_prints_its_reason(self, capsys: pytest.CaptureFixture[str]) -> None:
        AuditorRunReport().show(build_run())

        out = capsys.readouterr().out

        assert 'REJECT openverse:2' in out
        assert 'does not grant: resell' in out

    def test_a_pass_over_nothing_says_so(self, capsys: pytest.CaptureFixture[str]) -> None:
        AuditorRunReport().show(
            VerificationRun(run_id='run-2', outcomes=(), refusals_by_category=())
        )

        out = capsys.readouterr().out

        assert 'candidates=0' in out
        assert 'PUBLISH=0' in out
