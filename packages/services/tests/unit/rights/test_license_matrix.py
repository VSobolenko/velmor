from __future__ import annotations

import pytest

from packages.services.src.domain.license import StorefrontListing
from packages.services.src.rights.license_matrix import LicenseMatrix


class TestLicenseMatrixResolution:
    def test_resolves_canonical_spdx_identifier(self, matrix: LicenseMatrix) -> None:
        grant = matrix.resolve('CC-BY-4.0')

        assert grant is not None
        assert grant.license_id == 'CC-BY-4.0'

    def test_resolves_spdx_identifier_case_insensitively(self, matrix: LicenseMatrix) -> None:
        grant = matrix.resolve('mit')

        assert grant is not None
        assert grant.license_id == 'MIT'

    @pytest.mark.parametrize(
        ('raw', 'expected'),
        [
            ('cc0', 'CC0-1.0'),
            ('Public Domain', 'CC0-1.0'),
            ('apache 2.0', 'Apache-2.0'),
            ('gplv3', 'GPL-3.0-only'),
            ('cc by-nc', 'CC-BY-NC-4.0'),
            ('The Unlicense', 'Unlicense'),
        ],
    )
    def test_resolves_human_variants(self, matrix: LicenseMatrix, raw: str, expected: str) -> None:
        grant = matrix.resolve(raw)

        assert grant is not None
        assert grant.license_id == expected

    def test_strips_surrounding_whitespace_and_quotes(self, matrix: LicenseMatrix) -> None:
        grant = matrix.resolve('  "MIT"  ')

        assert grant is not None
        assert grant.license_id == 'MIT'

    @pytest.mark.parametrize('raw', [None, '', '   ', 'proprietary', 'all rights reserved'])
    def test_returns_none_for_unprovable_input(
        self, matrix: LicenseMatrix, raw: str | None
    ) -> None:
        assert matrix.resolve(raw) is None

    def test_does_not_treat_an_unknown_license_as_permissive(self, matrix: LicenseMatrix) -> None:
        assert matrix.resolve('totally-made-up-license') is None


class TestLicenseMatrixPolicy:
    def test_non_commercial_license_is_not_listed(self, matrix: LicenseMatrix) -> None:
        grant = matrix.resolve('CC-BY-NC-4.0')

        assert grant is not None
        assert grant.commercial_use_allowed is False
        assert grant.storefront_listing is StorefrontListing.NOT_LISTED

    def test_copyleft_license_allows_commercial_use_but_is_free_only(
        self, matrix: LicenseMatrix
    ) -> None:
        grant = matrix.resolve('GPL-3.0-only')

        assert grant is not None
        assert grant.commercial_use_allowed is True
        assert grant.storefront_listing is StorefrontListing.FREE_ONLY

    def test_no_derivatives_license_forbids_modification(self, matrix: LicenseMatrix) -> None:
        grant = matrix.resolve('CC-BY-ND-4.0')

        assert grant is not None
        assert grant.modification_allowed is False

    def test_attribution_license_carries_attribution_obligation(
        self, matrix: LicenseMatrix
    ) -> None:
        grant = matrix.resolve('CC-BY-4.0')

        assert grant is not None
        assert any('Credit the creator' in obligation for obligation in grant.obligations)

    def test_public_domain_dedication_carries_no_obligations(self, matrix: LicenseMatrix) -> None:
        grant = matrix.resolve('CC0-1.0')

        assert grant is not None
        assert grant.obligations == ()

    def test_every_policy_entry_is_reachable_by_its_own_identifier(
        self, matrix: LicenseMatrix
    ) -> None:
        for license_id in matrix.known_license_ids():
            assert matrix.resolve(license_id) is not None
