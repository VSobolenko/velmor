from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.verification_run import (
    CandidateOutcome,
    CategoryRefusal,
    VerificationOutcome,
    VerificationRun,
)
from packages.services.tests.conftest import build_record


def build_decision(candidate_id: str, publishable: bool, reasons: tuple[str, ...]) -> GateDecision:
    return GateDecision(
        candidate_id=candidate_id,
        publishable=publishable,
        reasons=reasons,
        record=build_record(),
    )


class TestCandidateOutcome:
    def test_a_published_outcome_carries_its_decision(self) -> None:
        decision = build_decision('openverse:1', publishable=True, reasons=())

        outcome = CandidateOutcome(
            candidate_id='openverse:1',
            outcome=VerificationOutcome.PUBLISHED,
            reasons=(),
            decision=decision,
        )

        assert outcome.decision is decision
        assert outcome.reasons == ()

    def test_a_refused_outcome_carries_its_reasons(self) -> None:
        decision = build_decision('openverse:1', publishable=False, reasons=('no licence',))

        outcome = CandidateOutcome(
            candidate_id='openverse:1',
            outcome=VerificationOutcome.REFUSED,
            reasons=decision.reasons,
            decision=decision,
        )

        assert outcome.reasons == ('no licence',)

    def test_a_screened_out_outcome_carries_no_decision(self) -> None:
        outcome = CandidateOutcome(
            candidate_id='openverse:2',
            outcome=VerificationOutcome.SCREENED_OUT,
            reasons=('Prohibited category matched: crack',),
            decision=None,
        )

        assert outcome.decision is None

    def test_a_paused_outcome_carries_no_decision(self) -> None:
        outcome = CandidateOutcome(
            candidate_id='openverse:3',
            outcome=VerificationOutcome.PAUSED,
            reasons=('Awaiting human review',),
            decision=None,
        )

        assert outcome.decision is None

    def test_an_unknown_outcome_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CandidateOutcome(
                candidate_id='openverse:1',
                outcome='probably_fine',
                reasons=(),
                decision=None,
            )


class TestVerificationRun:
    def test_every_outcome_of_a_pass_is_representable(self) -> None:
        published = build_decision('openverse:1', publishable=True, reasons=())
        refused = build_decision('openverse:2', publishable=False, reasons=('verdict is denied',))

        run = VerificationRun(
            run_id='run-1',
            outcomes=(
                CandidateOutcome(
                    candidate_id='openverse:1',
                    outcome=VerificationOutcome.PUBLISHED,
                    reasons=(),
                    decision=published,
                ),
                CandidateOutcome(
                    candidate_id='openverse:2',
                    outcome=VerificationOutcome.REFUSED,
                    reasons=refused.reasons,
                    decision=refused,
                ),
                CandidateOutcome(
                    candidate_id='openverse:3',
                    outcome=VerificationOutcome.SCREENED_OUT,
                    reasons=('Prohibited category matched: crack',),
                    decision=None,
                ),
                CandidateOutcome(
                    candidate_id='openverse:4',
                    outcome=VerificationOutcome.PAUSED,
                    reasons=('Awaiting human review',),
                    decision=None,
                ),
            ),
            refusals_by_category=(CategoryRefusal(category='crack', count=1),),
        )

        assert [outcome.outcome for outcome in run.outcomes] == [
            VerificationOutcome.PUBLISHED,
            VerificationOutcome.REFUSED,
            VerificationOutcome.SCREENED_OUT,
            VerificationOutcome.PAUSED,
        ]
        assert run.outcomes[1].reasons == ('verdict is denied',)
        assert run.refusals_by_category == (CategoryRefusal(category='crack', count=1),)

    def test_a_pass_with_nothing_to_report_is_representable(self) -> None:
        run = VerificationRun(run_id='run-2', outcomes=(), refusals_by_category=())

        assert run.outcomes == ()
        assert run.refusals_by_category == ()
