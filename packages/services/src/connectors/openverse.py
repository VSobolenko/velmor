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
            declared_license_id=self._spdx_from(item),
            declared_license_text=self._license_text_from(item),
            download_url=item.get('url'),
            size_bytes=item.get('filesize'),
        )

    @staticmethod
    def _spdx_from(item: dict) -> str | None:
        license_slug = item.get('license')
        if not license_slug:
            return None
        version = item.get('license_version')
        if version:
            return f'{license_slug}-{version}'
        return license_slug

    @staticmethod
    def _license_text_from(item: dict) -> str | None:
        license_url = item.get('license_url')
        if license_url:
            return license_url
        return item.get('license')
