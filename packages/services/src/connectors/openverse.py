from __future__ import annotations

import httpx

from packages.services.src.connectors.contract import SourceConnector
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.query import SearchQuery
from packages.services.src.domain.source import SourceSpec


class OpenverseConnector(SourceConnector):
    """Openverse image discovery.

    Openverse reports a machine-readable ``license`` per item, which is what makes
    it a tier A source. The query also asks Openverse itself to pre-filter to
    licenses that permit commercial use and modification, so the funnel starts
    narrower and fewer items are discarded later.
    """

    COMMERCIAL_AND_MODIFIABLE = 'commercial,modification'

    LICENSE_IDS: dict[tuple[str, str], str] = {
        ('cc0', '1.0'): 'CC0-1.0',
        ('by', '4.0'): 'CC-BY-4.0',
        ('by-sa', '4.0'): 'CC-BY-SA-4.0',
        ('by-nd', '4.0'): 'CC-BY-ND-4.0',
        ('by-nc', '4.0'): 'CC-BY-NC-4.0',
        ('by-nc-sa', '4.0'): 'CC-BY-NC-SA-4.0',
        ('by-nc-nd', '4.0'): 'CC-BY-NC-ND-4.0',
    }
    """Openverse's own license vocabulary, mapped onto the canonical identifiers.

    The source reports a slug - ``by``, ``by-sa``, ``cc0``, ``pdm``, ``sampling+`` -
    with the version in a separate field, and that is not an SPDX identifier. Only
    an exact ``(slug, version)`` pair maps: ``by`` at 4.0 is the license the policy
    table has an entry for, and the same slug at 2.0 is a different license with
    different terms, so an unlisted version is reported as it came and the matrix
    refuses it rather than resolving to a version nobody claimed.

    ``pdm`` (the Public Domain Mark) and the ``sampling`` licenses have no entry in
    the policy table, so they are deliberately absent here. They resolve to
    ``UNKNOWN`` and are refused, which is the honest outcome until the table gains
    an entry for them.
    """

    def __init__(self, spec: SourceSpec, http: httpx.AsyncClient) -> None:
        super().__init__(spec)
        self._http = http

    async def discover(self, query: SearchQuery) -> tuple[Candidate, ...]:
        response = await self._http.get(
            f'{self._spec.base_url}/images/',
            params={
                'q': query.text,
                'page_size': query.limit,
                'license_type': self.COMMERCIAL_AND_MODIFIABLE,
            },
        )
        response.raise_for_status()
        results = response.json()['results']
        return tuple(self._to_candidate(item) for item in results)

    def _to_candidate(self, item: dict) -> Candidate:
        return Candidate(
            id=f'{self._spec.id}:{item["id"]}',
            source_id=self._spec.id,
            title=item.get('title') or item['id'],
            landing_url=item['foreign_landing_url'],
            creator=item.get('creator'),
            content_type=item.get('category') or 'image',
            declared_license_id=self._declared_license_id(item),
            declared_license_text=self._license_text_from(item),
            download_url=item.get('url'),
            size_bytes=item.get('filesize'),
        )

    @classmethod
    def _declared_license_id(cls, item: dict) -> str | None:
        license_slug = item.get('license')
        if not license_slug:
            return None
        version = item.get('license_version')
        if version is None:
            return license_slug
        return cls.LICENSE_IDS.get((license_slug, version), f'{license_slug}-{version}')

    @staticmethod
    def _license_text_from(item: dict) -> str | None:
        license_url = item.get('license_url')
        if license_url:
            return license_url
        return item.get('license')
