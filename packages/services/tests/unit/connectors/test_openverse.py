from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from packages.services.src.connectors.openverse import OpenverseConnector
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.query import SearchQuery
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.tests.conftest import build_spec

QUERY = SearchQuery(text='vintage poster', limit=10)

# The slugs Openverse documents for its `license` field. The six CC families carry
# their version separately, so a slug and its version are the pair that identifies
# the license. These pairs are the ones the policy table has an entry for.
DOCUMENTED_LICENSES: tuple[tuple[str, str, str], ...] = (
    ('cc0', '1.0', 'CC0-1.0'),
    ('by', '4.0', 'CC-BY-4.0'),
    ('by-sa', '4.0', 'CC-BY-SA-4.0'),
    ('by-nd', '4.0', 'CC-BY-ND-4.0'),
    ('by-nc', '4.0', 'CC-BY-NC-4.0'),
    ('by-nc-sa', '4.0', 'CC-BY-NC-SA-4.0'),
    ('by-nc-nd', '4.0', 'CC-BY-NC-ND-4.0'),
)

# Documented slugs with no entry in the policy table. They must be reported as the
# source stated them and refused, never mapped onto a license they are not.
UNMODELLED_LICENSES: tuple[tuple[str, str, str], ...] = (
    ('pdm', '1.0', 'pdm-1.0'),
    ('sampling+', '1.0', 'sampling+-1.0'),
    ('nc-sampling+', '1.0', 'nc-sampling+-1.0'),
)


class TestOpenverseConnector:
    """The payload mapping, against the vocabulary and shape Openverse documents."""

    @staticmethod
    def item(**overrides: object) -> dict:
        """One image record, as the documented list response carries it."""
        return {
            'id': '4bc43a04-ef46-4544-a0c1-63c63f56e276',
            'title': 'Tree Bark Photo',
            'foreign_landing_url': 'https://stocksnap.io/photo/XNVBVXO3B7',
            'url': 'https://cdn.stocksnap.io/img-thumbs/960w/XNVBVXO3B7.jpg',
            'creator': 'Tim Sullivan',
            'license': 'by-sa',
            'license_version': '4.0',
            'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/',
            'category': 'photograph',
            'filesize': 896128,
        } | overrides

    async def discover(
        self, httpx_mock: HTTPXMock, **item_overrides: object
    ) -> tuple[Candidate, ...]:
        httpx_mock.add_response(json={'results': [self.item(**item_overrides)]})
        async with httpx.AsyncClient() as http:
            return await OpenverseConnector(build_spec(), http).discover(QUERY)

    async def test_the_record_maps_onto_a_candidate(self, httpx_mock: HTTPXMock) -> None:
        candidates = await self.discover(httpx_mock)

        assert candidates == (
            Candidate(
                id='openverse:4bc43a04-ef46-4544-a0c1-63c63f56e276',
                source_id='openverse',
                title='Tree Bark Photo',
                landing_url='https://stocksnap.io/photo/XNVBVXO3B7',
                creator='Tim Sullivan',
                content_type='photograph',
                declared_license_id='CC-BY-SA-4.0',
                declared_license_text='https://creativecommons.org/licenses/by-sa/4.0/',
                download_url='https://cdn.stocksnap.io/img-thumbs/960w/XNVBVXO3B7.jpg',
                size_bytes=896128,
            ),
        )

    async def test_the_query_asks_for_commercially_usable_and_modifiable_media(
        self, httpx_mock: HTTPXMock
    ) -> None:
        await self.discover(httpx_mock)

        params = httpx_mock.get_requests()[0].url.params
        assert params['q'] == 'vintage poster'
        assert params['page_size'] == '10'
        assert params['license_type'] == 'commercial,modification'

    @pytest.mark.parametrize(('slug', 'version', 'expected'), DOCUMENTED_LICENSES)
    async def test_a_documented_license_reaches_the_policy_table(
        self, httpx_mock: HTTPXMock, matrix: LicenseMatrix, slug: str, version: str, expected: str
    ) -> None:
        candidates = await self.discover(httpx_mock, license=slug, license_version=version)

        assert candidates[0].declared_license_id == expected
        # The point of the mapping: the identifier has to resolve, or every item
        # from the source is refused as unknown.
        assert matrix.resolve(candidates[0].declared_license_id) is not None

    @pytest.mark.parametrize(('slug', 'version', 'expected'), UNMODELLED_LICENSES)
    async def test_a_license_the_policy_table_lacks_is_reported_as_it_came(
        self, httpx_mock: HTTPXMock, matrix: LicenseMatrix, slug: str, version: str, expected: str
    ) -> None:
        candidates = await self.discover(httpx_mock, license=slug, license_version=version)

        assert candidates[0].declared_license_id == expected
        assert matrix.resolve(candidates[0].declared_license_id) is None

    async def test_a_version_the_policy_table_lacks_is_not_widened_to_another_one(
        self, httpx_mock: HTTPXMock, matrix: LicenseMatrix
    ) -> None:
        candidates = await self.discover(httpx_mock, license='by-sa', license_version='2.0')

        assert candidates[0].declared_license_id == 'by-sa-2.0'
        assert matrix.resolve(candidates[0].declared_license_id) is None

    async def test_a_missing_license_field_records_no_license(self, httpx_mock: HTTPXMock) -> None:
        candidates = await self.discover(httpx_mock, license=None, license_version=None)

        assert candidates[0].declared_license_id is None

    async def test_a_null_license_version_is_reported_without_a_guess(
        self, httpx_mock: HTTPXMock, matrix: LicenseMatrix
    ) -> None:
        candidates = await self.discover(httpx_mock, license='by', license_version=None)

        assert candidates[0].declared_license_id == 'by'
        assert matrix.resolve(candidates[0].declared_license_id) is None

    async def test_a_response_without_results_raises(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={})

        async with httpx.AsyncClient() as http:
            with pytest.raises(KeyError):
                await OpenverseConnector(build_spec(), http).discover(QUERY)

    async def test_a_record_without_an_id_raises_rather_than_storing_a_partial_candidate(
        self, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(json={'results': [{'title': 'No identifier'}]})

        async with httpx.AsyncClient() as http:
            with pytest.raises(KeyError):
                await OpenverseConnector(build_spec(), http).discover(QUERY)

    async def test_an_error_response_is_not_swallowed(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=500)

        async with httpx.AsyncClient() as http:
            with pytest.raises(httpx.HTTPStatusError):
                await OpenverseConnector(build_spec(), http).discover(QUERY)
