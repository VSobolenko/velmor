from __future__ import annotations

import hashlib

import httpx

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.errors import DeliveryRefusedError
from packages.services.src.domain.catalogue import CatalogueEntry
from packages.services.src.domain.delivery import DeliveryResult
from packages.services.src.domain.entitlement import Entitlement, EntitlementState
from packages.services.src.persistence.contract import (
    CatalogueEntryRepository,
    EntitlementRepository,
)


class DeliveryService:
    """Deliver origin bytes to an entitled buyer with integrity and concealment."""

    def __init__(
        self,
        entitlements: EntitlementRepository,
        entries: CatalogueEntryRepository,
        cache: AssetCache,
        http: httpx.AsyncClient,
    ) -> None:
        self._entitlements = entitlements
        self._entries = entries
        self._cache = cache
        self._http = http

    async def deliver(self, buyer_id: str, candidate_id: str) -> DeliveryResult:
        await self._require_active_entitlement(buyer_id, candidate_id)
        entry = await self._require_entry(candidate_id)
        cached = self._cache.get(entry.content_digest)
        if cached is not None and hashlib.sha256(cached).hexdigest() == entry.content_digest:
            return self._result_from(entry, cached)
        body = await self._fetch_origin(entry)
        digest = hashlib.sha256(body).hexdigest()
        if digest != entry.content_digest:
            raise DeliveryRefusedError(
                'the file no longer matches the recorded digest'
            )
        if len(body) <= self._cache.max_bytes:
            self._cache.put(digest, body)
        return self._result_from(entry, body)

    async def _require_active_entitlement(self, buyer_id: str, candidate_id: str) -> None:
        rows = await self._entitlements.for_buyer_candidate(buyer_id, candidate_id)
        if any(row.state is EntitlementState.ACTIVE for row in rows):
            return
        revoked = tuple(row for row in rows if row.state is EntitlementState.REVOKED)
        if revoked:
            latest = self._most_recent_revoked(revoked)
            reason = latest.revocation_reason
            if reason is None:
                raise DeliveryRefusedError('entitlement revoked')
            raise DeliveryRefusedError(f'entitlement revoked: {reason}')
        raise DeliveryRefusedError('the buyer has no entitlement for this good')

    async def _require_entry(self, candidate_id: str) -> CatalogueEntry:
        entry = await self._entries.by_candidate(candidate_id)
        if entry is None:
            raise DeliveryRefusedError('the good is unknown to the catalogue')
        return entry

    async def _fetch_origin(self, entry: CatalogueEntry) -> bytes:
        try:
            response = await self._http.get(entry.origin_url, follow_redirects=True)
        except httpx.RequestError as error:
            # httpx reports a transport-level failure - connection refused, DNS
            # failure, read timeout - by raising a RequestError subclass. This
            # repository already relies on that contract and names it at
            # packages/auditor/src/nodes/investigate.py:47-49 (and the Saleor
            # client / ContentDigest). Mapping to DeliveryRefusedError is the
            # delivery refusal; the message must not interpolate the origin URL.
            raise DeliveryRefusedError('the origin could not be reached') from error
        if response.status_code != 200:
            raise DeliveryRefusedError(
                f'the origin returned HTTP {response.status_code}'
            )
        return response.content

    @staticmethod
    def _most_recent_revoked(revoked: tuple[Entitlement, ...]) -> Entitlement:
        return max(
            revoked,
            key=lambda row: (row.revoked_at, row.order_id),
        )

    @staticmethod
    def _result_from(entry: CatalogueEntry, payload: bytes) -> DeliveryResult:
        return DeliveryResult(
            candidate_id=entry.candidate_id,
            payload=payload,
            content_digest=entry.content_digest,
            license_id=entry.license_id,
            obligations=entry.obligations,
        )
