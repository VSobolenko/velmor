from __future__ import annotations

import hashlib

import httpx

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.errors import DigestUnavailableError
from packages.services.src.domain.digest import DigestResult

DIGEST_ALGORITHM = 'sha256'


class ContentDigest:
    """Obtain a SHA-256 digest of the origin file, caching small payloads."""

    def __init__(self, http: httpx.AsyncClient, cache: AssetCache) -> None:
        self._http = http
        self._cache = cache

    async def obtain(self, download_url: str) -> DigestResult:
        if download_url.strip() == '':
            raise DigestUnavailableError('no download URL is available for a digest')

        try:
            response = await self._http.get(download_url, follow_redirects=True)
        except httpx.RequestError as error:
            # httpx reports a transport-level failure - connection refused, DNS
            # failure, read timeout - by raising a RequestError subclass. This
            # repository already relies on that contract and names it at
            # packages/auditor/src/nodes/investigate.py:47-49 (and the Saleor
            # client). Handling the refusal as DigestUnavailableError is the
            # publication contract; there is no status to branch on.
            raise DigestUnavailableError(
                f'digest could not be obtained from {download_url}: {error}'
            ) from error

        if response.status_code != 200:
            raise DigestUnavailableError(
                f'digest could not be obtained from {download_url}: '
                f'HTTP {response.status_code}'
            )

        body = response.content
        digest = hashlib.sha256(body).hexdigest()
        size_bytes = len(body)
        if size_bytes <= self._cache.max_bytes:
            self._cache.put(digest, body)
            return DigestResult(digest=digest, size_bytes=size_bytes, cached=True)
        return DigestResult(digest=digest, size_bytes=size_bytes, cached=False)
