from __future__ import annotations

import pytest

from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.rights import EvidenceKind
from packages.services.src.domain.source import SourceKind, SourceSpec, SourceTier
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.tests.conftest import build_record


@pytest.fixture
def tier_c_spec() -> SourceSpec:
    return SourceSpec(
        id='opaque-shop',
        name='Opaque Shop',
        kind=SourceKind.SITEMAP,
        tier=SourceTier.C,
        base_url='https://example.test',
        required_env=(),
        enabled=True,
    )


class TestPublicationGateAllows:
    def test_publishes_when_every_condition_holds(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        decision = gate.decide(tier_a_spec, build_record())

        assert decision.publishable is True
        assert decision.reasons == ()

    def test_reports_paid_placement_for_a_permissive_license(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        record = build_record(license_id='MIT')

        assert gate.listing_for(record) is StorefrontListing.PAID_OK

    def test_copyleft_is_publishable_but_not_for_sale(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        record = build_record(license_id='GPL-3.0-only')

        decision = gate.decide(tier_a_spec, record)

        assert decision.publishable is True
        assert gate.listing_for(record) is StorefrontListing.FREE_ONLY


class TestPublicationGateDenies:
    def test_tier_c_source_can_never_auto_publish(
        self, gate: PublicationGate, tier_c_spec: SourceSpec
    ) -> None:
        decision = gate.decide(tier_c_spec, build_record())

        assert decision.publishable is False
        assert any('tier C' in reason for reason in decision.reasons)
        assert any('machine-readable' in reason for reason in decision.reasons)

    @pytest.mark.parametrize('verdict', ['denied', 'unknown'])
    def test_non_allowed_verdict_is_rejected(
        self, gate: PublicationGate, tier_a_spec: SourceSpec, verdict: str
    ) -> None:
        decision = gate.decide(tier_a_spec, build_record(verdict=verdict))

        assert decision.publishable is False
        assert any('verdict is' in reason for reason in decision.reasons)

    def test_missing_license_identity_is_rejected(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        decision = gate.decide(tier_a_spec, build_record(license_id=None))

        assert decision.publishable is False
        assert any('No license identity' in reason for reason in decision.reasons)

    def test_license_outside_the_policy_table_is_rejected(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        decision = gate.decide(tier_a_spec, build_record(license_id='Some-Unlisted-1.0'))

        assert decision.publishable is False
        assert any('not in the policy table' in reason for reason in decision.reasons)

    def test_interpretation_only_evidence_is_rejected(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        record = build_record(evidence_kinds=(EvidenceKind.LLM_EXTRACTION, EvidenceKind.SPDX_MATCH))

        decision = gate.decide(tier_a_spec, record)

        assert decision.publishable is False
        assert any('only on interpretation' in reason for reason in decision.reasons)

    def test_human_attestation_resolves_identity_ambiguity(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        record = build_record(
            evidence_kinds=(EvidenceKind.HUMAN_ATTESTATION, EvidenceKind.SPDX_MATCH)
        )

        decision = gate.decide(tier_a_spec, record)

        assert decision.publishable is True

    def test_a_human_ruling_cannot_override_the_policy_table(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        record = build_record(
            license_id='CC-BY-NC-4.0',
            evidence_kinds=(EvidenceKind.HUMAN_ATTESTATION, EvidenceKind.SPDX_MATCH),
        )

        decision = gate.decide(tier_a_spec, record)

        assert decision.publishable is False
        assert any('commercial catalog' in reason for reason in decision.reasons)

    def test_evidence_without_an_identity_match_is_rejected(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        record = build_record(evidence_kinds=(EvidenceKind.SOURCE_API_FIELD,))

        decision = gate.decide(tier_a_spec, record)

        assert decision.publishable is False
        assert any('never matched' in reason for reason in decision.reasons)

    def test_no_evidence_at_all_is_rejected(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        decision = gate.decide(tier_a_spec, build_record(evidence_kinds=()))

        assert decision.publishable is False
        assert len(decision.reasons) >= 2

    def test_non_commercial_license_is_not_listed(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        record = build_record(license_id='CC-BY-NC-4.0')

        decision = gate.decide(tier_a_spec, record)

        assert decision.publishable is False
        assert any('commercial catalog' in reason for reason in decision.reasons)
        assert gate.listing_for(record) is StorefrontListing.NOT_LISTED

    def test_every_rejection_explains_itself(
        self, gate: PublicationGate, tier_c_spec: SourceSpec
    ) -> None:
        decision = gate.decide(tier_c_spec, build_record(verdict='unknown', license_id=None))

        assert decision.publishable is False
        assert len(decision.reasons) >= 3
        assert all(reason for reason in decision.reasons)

    def test_undecidable_license_has_no_listing(
        self, gate: PublicationGate, tier_a_spec: SourceSpec
    ) -> None:
        assert gate.listing_for(build_record(license_id=None)) is StorefrontListing.NOT_LISTED
