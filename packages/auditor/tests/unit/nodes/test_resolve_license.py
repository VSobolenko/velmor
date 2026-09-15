from __future__ import annotations

from packages.auditor.src.nodes.resolve_license import ResolveLicenseNode
from packages.auditor.tests.conftest import FixedClock, build_state
from packages.services.src.domain.interpretation import LicenseInterpretation
from packages.services.src.domain.review import HumanRuling
from packages.services.src.domain.rights import EvidenceKind
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.tests.conftest import build_candidate, build_evidence, build_spec

INTERPRETED = LicenseInterpretation(
    license_claim='MIT',
    confidence=0.9,
    quoted_text='This work is released under the MIT license.',
    reasoning='the page names the MIT license',
)


class TestResolveLicenseNode:
    async def test_a_declared_licence_resolves_and_records_the_identity_match(
        self, clock: FixedClock, matrix: LicenseMatrix
    ) -> None:
        node = ResolveLicenseNode(matrix, clock)
        state = build_state(build_candidate(license_id='CC0-1.0'), build_spec())

        result = await node(state)

        assert result['resolved_license_id'] == 'CC0-1.0'
        evidence = result['evidence']
        assert [item.kind for item in evidence] == [EvidenceKind.SPDX_MATCH]
        assert evidence[0].excerpt == 'CC0-1.0'
        assert evidence[0].retrieved_at == clock.now()

    async def test_a_model_reading_outranks_the_declared_field(
        self, clock: FixedClock, matrix: LicenseMatrix
    ) -> None:
        node = ResolveLicenseNode(matrix, clock)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            interpretation=INTERPRETED,
        )

        result = await node(state)

        assert result['resolved_license_id'] == 'MIT'

    async def test_a_human_ruling_outranks_a_model_reading(
        self, clock: FixedClock, matrix: LicenseMatrix
    ) -> None:
        node = ResolveLicenseNode(matrix, clock)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            interpretation=INTERPRETED,
            human_ruling=HumanRuling(approved=True, license_id='Apache-2.0', note='checked'),
        )

        result = await node(state)

        assert result['resolved_license_id'] == 'Apache-2.0'

    async def test_a_rejected_ruling_resolves_nothing(
        self, clock: FixedClock, matrix: LicenseMatrix
    ) -> None:
        node = ResolveLicenseNode(matrix, clock)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            human_ruling=HumanRuling(approved=False, license_id=None, note='not reusable'),
        )

        result = await node(state)

        assert result == {'resolved_license_id': None}

    async def test_an_unrecognised_claim_resolves_to_nothing_and_matches_no_identity(
        self, clock: FixedClock, matrix: LicenseMatrix
    ) -> None:
        node = ResolveLicenseNode(matrix, clock)
        state = build_state(
            build_candidate(license_id='Free for personal use only, ask the author'),
            build_spec(),
        )

        result = await node(state)

        assert result == {'resolved_license_id': None}

    async def test_earlier_evidence_is_kept_and_the_identity_match_is_appended(
        self, clock: FixedClock, matrix: LicenseMatrix
    ) -> None:
        node = ResolveLicenseNode(matrix, clock)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            interpretation=INTERPRETED,
            evidence=build_evidence((EvidenceKind.LLM_EXTRACTION,), excerpt='MIT'),
        )

        result = await node(state)

        assert [item.kind for item in result['evidence']] == [
            EvidenceKind.LLM_EXTRACTION,
            EvidenceKind.SPDX_MATCH,
        ]

    async def test_the_node_returns_only_the_keys_it_changes(
        self, clock: FixedClock, matrix: LicenseMatrix
    ) -> None:
        node = ResolveLicenseNode(matrix, clock)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            interpretation=INTERPRETED,
        )

        result = await node(state)

        assert set(result) == {'resolved_license_id', 'evidence'}
