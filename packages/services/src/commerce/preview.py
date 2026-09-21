from __future__ import annotations

import hashlib

import httpx

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.commerce.errors import (
    PreviewCoverMissingError,
    PreviewDigestMismatchError,
    PreviewNotFoundError,
    PreviewOriginUnreachableError,
)
from packages.services.src.domain.catalogue import CatalogueEntry, SaleableEntry
from packages.services.src.domain.preview import CatalogueCover, PreviewImage
from packages.services.src.persistence.contract import (
    CatalogueCoverRepository,
    CatalogueEntryRepository,
)


class GoodPreview:
    """Bytes to serve for a good's preview, derived from the good or its cover.

    The delivery rule is applied here unchanged: the bytes must hash to the
    digest recorded at publication. A preview is the first time origin bytes
    leave this host before payment, so it is preferred from our own cache,
    otherwise fetched and verified, then downscaled and served from our own
    cache, and the origin location appears in no response, no header and no
    error message.

    Nothing here decides what may be sold either: only an entry the catalogue
    holds as ``PUBLISHED`` and ``PAID_OK`` has a preview, so the endpoint cannot
    become a way to read a good the gate refused.
    """

    def __init__(
        self,
        entries: CatalogueEntryRepository,
        covers: CatalogueCoverRepository,
        cache: AssetCache,
        http: httpx.AsyncClient,
        derivative: PreviewDerivative,
    ) -> None:
        self._entries = entries
        self._covers = covers
        self._cache = cache
        self._http = http
        self._derivative = derivative

    async def render(self, candidate_id: str) -> PreviewImage:
        entry = await self._require_saleable_entry(candidate_id)
        cover = await self._covers.cover_for(candidate_id)
        if cover is not None:
            return self._from_cover(cover)
        return await self._derivative_of(entry)

    async def _require_saleable_entry(self, candidate_id: str) -> CatalogueEntry:
        entry = await self._entries.by_candidate(candidate_id)
        if entry is None or not SaleableEntry.matches(entry):
            raise PreviewNotFoundError('no preview exists for this good')
        return entry

    def _from_cover(self, cover: CatalogueCover) -> PreviewImage:
        payload = self._derivative.cached(cover.digest)
        if payload is None:
            raise PreviewCoverMissingError(
                'a cover is recorded for this good but its bytes are not cached'
            )
        return PreviewImage(
            payload=payload,
            media_type=cover.media_type,
            etag=self._etag(cover.digest),
            from_cover=True,
        )

    async def _derivative_of(self, entry: CatalogueEntry) -> PreviewImage:
        cached = self._derivative.cached(entry.content_digest)
        if cached is not None:
            return self._image(cached, entry.content_digest)
        body = await self._original(entry)
        return self._image(
            self._derivative.cut(entry.content_digest, body), entry.content_digest
        )

    async def _original(self, entry: CatalogueEntry) -> bytes:
        """The good's bytes, from our cache when they are there, else the origin.

        A cached file is re-hashed rather than trusted because its name is not
        proof of its content; this is the same test ``DeliveryService`` applies
        to the same cache before it hands bytes to a buyer.
        """
        cached = self._cache.get(entry.content_digest)
        if cached is not None and hashlib.sha256(cached).hexdigest() == entry.content_digest:
            return cached
        body = await self._fetch_origin(entry)
        digest = hashlib.sha256(body).hexdigest()
        if digest != entry.content_digest:
            raise PreviewDigestMismatchError(
                'the origin bytes no longer match the digest recorded at publication'
            )
        if len(body) <= self._cache.max_bytes:
            self._cache.put(digest, body)
        return body

    async def _fetch_origin(self, entry: CatalogueEntry) -> bytes:
        try:
            response = await self._http.get(entry.origin_url, follow_redirects=True)
        except httpx.RequestError as error:
            # Authorized catch (rule 03 case 3). The contract is two-part and both
            # parts are documented sources, not a neighbouring file: httpx names
            # RequestError as the base class for a transport-level failure -
            # connection refused, DNS failure, read timeout - in its exceptions
            # reference, and the preview table in
            # .superpowers/sdd/redesign-storefront-ux/contract.md fixes 502 for an
            # unreachable origin. Answering 502 is the logic, so the contracted
            # response cannot be produced without observing this failure.
            # Alternatives ruled out: letting it propagate answers 500 where the
            # contract says 502, and no predicate answers "will this request
            # succeed" other than attempting it.
            #
            # This stands on the contract above and not on the similar catch in
            # packages/auditor/src/nodes/investigate.py. An existing try/except is
            # grandfathered, never a precedent (rule 03), so that file is not
            # cited here as authorization for this one.
            #
            # The cause is chained deliberately: the operator's log keeps the
            # origin for diagnosis. What must not name the origin is the buyer's
            # response, and that is guaranteed separately - the API's refusal
            # handler closes over a fixed detail - and asserted by
            # test_the_origin_url_appears_in_no_response.
            raise PreviewOriginUnreachableError('the origin could not be reached') from error
        if response.status_code != 200:
            raise PreviewOriginUnreachableError('the origin could not be reached')
        return response.content

    @staticmethod
    def _etag(digest: str) -> str:
        return f'"{digest}"'

    def _image(self, payload: bytes, digest: str) -> PreviewImage:
        return PreviewImage(
            payload=payload,
            media_type=self._derivative.media_type,
            etag=self._etag(digest),
            from_cover=False,
        )
