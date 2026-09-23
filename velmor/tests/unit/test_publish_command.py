from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.api.tests.unit.configs.test_settings import TestCommerceSettings
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.services.src.commerce.image_payload import ImagePayload
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.publication import PublicationAction, PublicationOutcome
from packages.services.src.domain.rights import EvidenceKind, RightsRecord
from packages.services.src.domain.source import SourceSpec
from packages.services.src.rights.license_grants import DefaultLicenseGrants
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.src.rights.rights_resolver import RightsResolver
from packages.services.tests.conftest import build_candidate, build_record
from velmor.publish import PublishCommand

CANDIDATE_ID = 'openverse:ce7c97e3-e1dc-4576-874c-c981cb49d04e'
ORIGIN_URL = 'https://upload.wikimedia.org/wikipedia/commons/7/77/Larch.svg'
PUBLISHED_AT = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)

SUPERSEDED_ENGINE = '1.1.0'
"""The engine that produced every record on sale when this report was added."""


def build_loader(tmp_path: Path) -> SettingsLoader:
    """A loader over a complete, fictional .env, so no bootstrap failure hides the report."""
    values = {**TestCommerceSettings.BASELINE_VALUES, **TestCommerceSettings.COMMERCE_VALUES}
    env_file = tmp_path / '.env.test'
    env_file.write_text('\n'.join(f'{key}={value}' for key, value in values.items()))
    return SettingsLoader(env_file)


def published_entry(candidate_id: str) -> CatalogueEntry:
    """A catalogue row as the bridge leaves it behind a successful publish."""
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id='product-published',
        saleor_variant_id='variant-published',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=(),
        listing=StorefrontListing.PAID_OK,
        state=CatalogueEntryState.PUBLISHED,
        withdrawal_reason=None,
        published_at=PUBLISHED_AT,
        content_digest='00' * 32,
        origin_url=ORIGIN_URL,
    )


def no_source_evidence_record() -> RightsRecord:
    """The cheapest record the gate refuses: a model reading and the match derived from it."""
    return build_record(
        evidence_kinds=(EvidenceKind.LLM_EXTRACTION, EvidenceKind.SPDX_MATCH)
    )


class PublishedPairsStore:
    """The one store call the publish loop makes: the pairs it will publish."""

    def __init__(self, pairs: tuple[tuple[Candidate, RightsRecord], ...]) -> None:
        self._pairs = pairs

    async def published(self, limit: int) -> tuple[tuple[Candidate, RightsRecord], ...]:
        return self._pairs


class RecordingBridge:
    """Records the decision it was handed and answers as the real bridge would.

    The bridge's own behaviour is verified in
    ``packages/services/tests/unit/commerce/test_publication.py``. What these tests
    read is which decision reaches the bridge and what the operator's report then
    says, so the outcome follows the decision under test.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[Candidate, GateDecision, SourceSpec, datetime]] = []

    async def apply(
        self,
        candidate: Candidate,
        decision: GateDecision,
        spec: SourceSpec,
        now: datetime,
    ) -> PublicationOutcome:
        self.calls.append((candidate, decision, spec, now))
        if decision.publishable:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.PUBLISHED,
                reasons=(),
                entry=published_entry(candidate.id),
            )
        return PublicationOutcome(
            candidate_id=candidate.id,
            action=PublicationAction.REFUSED,
            reasons=decision.reasons,
            entry=None,
        )


@pytest.fixture
def gate() -> PublicationGate:
    return PublicationGate(LicenseMatrix(DefaultLicenseGrants.TABLE))


class TestPublishOutcomeReport:
    """What the operator reads for a withdrawal, printed by the publish loop."""

    def test_a_withdrawal_prints_the_candidate_the_action_and_the_reason(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        command = PublishCommand(build_loader(tmp_path))

        command._log_outcome(
            CANDIDATE_ID,
            PublicationAction.WITHDRAWN,
            (ImagePayload.NOT_RENDERABLE_REASON,),
        )

        out = capsys.readouterr().out

        assert CANDIDATE_ID in out
        assert PublicationAction.WITHDRAWN.value in out
        assert ImagePayload.NOT_RENDERABLE_REASON in out

    def test_the_reported_line_names_no_origin(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        command = PublishCommand(build_loader(tmp_path))

        command._log_outcome(
            CANDIDATE_ID,
            PublicationAction.WITHDRAWN,
            (ImagePayload.NOT_RENDERABLE_REASON,),
        )

        out = capsys.readouterr().out

        assert ORIGIN_URL not in out
        assert 'http://' not in out
        assert 'https://' not in out


class TestThePublishLoopDerivesItsDecision:
    """The decision handed to the bridge is the gate's output, not an assertion."""

    async def test_a_refused_record_is_reported_from_the_gates_own_ruling(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        gate: PublicationGate,
    ) -> None:
        command = PublishCommand(build_loader(tmp_path))
        candidate = build_candidate()
        record = no_source_evidence_record()
        store = PublishedPairsStore(((candidate, record),))
        bridge = RecordingBridge()

        await command._publish_all(store, bridge, gate, 200)

        recorded_candidate, decision, spec, _ = bridge.calls[0]
        assert recorded_candidate is candidate
        assert spec.id == candidate.source_id
        assert decision == gate.decide(spec, record)
        assert decision.publishable is False
        assert decision.reasons != ()
        out = capsys.readouterr().out
        reasons = '; '.join(decision.reasons)
        assert (
            f'{PublicationAction.REFUSED.value:<10} {candidate.id}: {reasons}' in out
        )


class TestTheEngineVersionOfTheRulingIsReported:
    """A ruling the running engine did not produce is reported, never refused."""

    async def test_a_superseded_ruling_keeps_its_action_and_carries_the_reason(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        gate: PublicationGate,
    ) -> None:
        assert SUPERSEDED_ENGINE != RightsResolver.ENGINE_VERSION
        command = PublishCommand(build_loader(tmp_path))
        candidate = build_candidate()
        record = build_record().model_copy(
            update={'engine_version': SUPERSEDED_ENGINE}
        )
        store = PublishedPairsStore(((candidate, record),))
        bridge = RecordingBridge()

        await command._publish_all(store, bridge, gate, 200)

        _, decision, _, _ = bridge.calls[0]
        assert decision.publishable is True
        line = next(
            line
            for line in capsys.readouterr().out.splitlines()
            if candidate.id in line
        )
        assert line.startswith(PublicationAction.PUBLISHED.value)
        assert SUPERSEDED_ENGINE in line
        assert RightsResolver.ENGINE_VERSION in line

    async def test_a_ruling_from_the_running_engine_carries_no_such_reason(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        gate: PublicationGate,
    ) -> None:
        command = PublishCommand(build_loader(tmp_path))
        candidate = build_candidate()
        record = build_record()
        assert record.engine_version == RightsResolver.ENGINE_VERSION
        store = PublishedPairsStore(((candidate, record),))
        bridge = RecordingBridge()

        await command._publish_all(store, bridge, gate, 200)

        line = next(
            line
            for line in capsys.readouterr().out.splitlines()
            if candidate.id in line
        )
        assert line == f'{PublicationAction.PUBLISHED.value:<10} {candidate.id}'
