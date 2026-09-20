from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.errors import DeliveryRefusedError
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.delivery import DeliveryResult
from packages.services.src.domain.entitlement import Entitlement, EntitlementState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.persistence.memory import InMemoryStore

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)
ORIGIN_URL = 'https://secret-origin.example/never-leak/asset.bin'
BUYER_ID = 'buyer-1'
CANDIDATE_ID = 'openverse:1'
PAYLOAD = b'entitled-asset-bytes'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
OBLIGATIONS: tuple[str, ...] = ('Credit the creator', 'Link to the license text')


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def build_entry(
    *,
    state: CatalogueEntryState = CatalogueEntryState.PUBLISHED,
    content_digest: str = DIGEST,
    origin_url: str = ORIGIN_URL,
    license_id: str | None = 'CC-BY-4.0',
    obligations: tuple[str, ...] = OBLIGATIONS,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=CANDIDATE_ID,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=None,
        license_id=license_id,
        obligations=obligations,
        listing=StorefrontListing.PAID_OK,
        state=state,
        withdrawal_reason='withdrawn for test' if state is CatalogueEntryState.WITHDRAWN else None,
        published_at=EARLIER,
        content_digest=content_digest,
        origin_url=origin_url,
    )


def build_entitlement(
    *,
    state: EntitlementState = EntitlementState.ACTIVE,
    order_id: str = 'order-1',
    revoked_at: datetime | None = None,
    revocation_reason: str | None = None,
) -> Entitlement:
    return Entitlement(
        buyer_id=BUYER_ID,
        candidate_id=CANDIDATE_ID,
        order_id=order_id,
        granted_at=EARLIER,
        state=state,
        revoked_at=revoked_at,
        revocation_reason=revocation_reason,
    )


def assert_no_origin_in_dump(result: DeliveryResult) -> None:
    dumped = result.model_dump()
    assert 'origin_url' not in dumped
    assert 'download_url' not in dumped
    for value in dumped.values():
        assert ORIGIN_URL not in str(value)


def assert_no_origin_in_error(error: BaseException) -> None:
    assert ORIGIN_URL not in str(error)


class TestDeliveryService:
    async def test_entitled_buyer_cache_miss_origin_ok(self, tmp_path: Path) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        await store.save_entitlement(build_entitlement())
        origin_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal origin_calls
            origin_calls += 1
            assert str(request.url) == ORIGIN_URL
            return httpx.Response(200, content=PAYLOAD)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            result = await service.deliver(BUYER_ID, CANDIDATE_ID)

        assert result.payload == PAYLOAD
        assert result.content_digest == DIGEST
        assert result.candidate_id == CANDIDATE_ID
        assert result.license_id == 'CC-BY-4.0'
        assert result.obligations == OBLIGATIONS
        assert origin_calls == 1
        assert cache.get(DIGEST) == PAYLOAD
        assert_no_origin_in_dump(result)

    async def test_cache_hit_skips_origin(self, tmp_path: Path) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        await store.save_entitlement(build_entitlement())
        origin_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal origin_calls
            origin_calls += 1
            return httpx.Response(200, content=PAYLOAD)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        cache.put(DIGEST, PAYLOAD)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            result = await service.deliver(BUYER_ID, CANDIDATE_ID)

        assert result.payload == PAYLOAD
        assert origin_calls == 0
        assert_no_origin_in_dump(result)

    async def test_no_entitlement_refuses_without_origin(self, tmp_path: Path) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        origin_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal origin_calls
            origin_calls += 1
            return httpx.Response(200, content=PAYLOAD)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            with pytest.raises(DeliveryRefusedError) as raised:
                await service.deliver(BUYER_ID, CANDIDATE_ID)

        assert 'no entitlement' in str(raised.value).lower()
        assert origin_calls == 0
        assert_no_origin_in_error(raised.value)

    async def test_revoked_only_refuses_with_reason(self, tmp_path: Path) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        reason = 'payment refunded by operator'
        await store.save_entitlement(
            build_entitlement(
                state=EntitlementState.REVOKED,
                revoked_at=NOW,
                revocation_reason=reason,
            )
        )
        origin_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal origin_calls
            origin_calls += 1
            return httpx.Response(200, content=PAYLOAD)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            with pytest.raises(DeliveryRefusedError) as raised:
                await service.deliver(BUYER_ID, CANDIDATE_ID)

        assert reason in str(raised.value)
        assert origin_calls == 0
        assert_no_origin_in_error(raised.value)

    async def test_origin_http_error_conceals_url(self, tmp_path: Path) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        await store.save_entitlement(build_entitlement())

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, content=b'boom')

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            with pytest.raises(DeliveryRefusedError) as raised:
                await service.deliver(BUYER_ID, CANDIDATE_ID)

        assert '500' in str(raised.value)
        assert_no_origin_in_error(raised.value)

    async def test_origin_transport_error_conceals_url(self, tmp_path: Path) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        await store.save_entitlement(build_entitlement())

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError('refused', request=request)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            with pytest.raises(DeliveryRefusedError) as raised:
                await service.deliver(BUYER_ID, CANDIDATE_ID)

        assert raised.value.__cause__ is not None
        assert isinstance(raised.value.__cause__, httpx.ConnectError)
        assert_no_origin_in_error(raised.value)

    async def test_digest_mismatch_refuses_and_does_not_cache(
        self, tmp_path: Path
    ) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        await store.save_entitlement(build_entitlement())
        bad_payload = b'different-bytes-from-origin'

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=bad_payload)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            with pytest.raises(DeliveryRefusedError) as raised:
                await service.deliver(BUYER_ID, CANDIDATE_ID)

        assert 'does not match' in str(raised.value).lower() or 'no longer matches' in str(
            raised.value
        ).lower()
        assert cache.get(DIGEST) is None
        assert cache.get(hashlib.sha256(bad_payload).hexdigest()) is None
        rows = await store.for_buyer_candidate(BUYER_ID, CANDIDATE_ID)
        assert len(rows) == 1
        assert rows[0].state is EntitlementState.ACTIVE
        assert_no_origin_in_error(raised.value)

    async def test_withdrawn_entry_with_active_entitlement_delivers(
        self, tmp_path: Path
    ) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry(state=CatalogueEntryState.WITHDRAWN))
        await store.save_entitlement(build_entitlement())

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=PAYLOAD)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            result = await service.deliver(BUYER_ID, CANDIDATE_ID)

        assert result.payload == PAYLOAD
        assert_no_origin_in_dump(result)

    @pytest.mark.parametrize(
        'mode',
        (
            'success',
            'no_entitlement',
            'revoked',
            'http_error',
            'transport_error',
            'digest_mismatch',
        ),
    )
    async def test_concealment_origin_url_absent(self, tmp_path: Path, mode: str) -> None:
        store = InMemoryStore()
        await store.save_entry(build_entry())
        if mode != 'no_entitlement':
            if mode == 'revoked':
                await store.save_entitlement(
                    build_entitlement(
                        state=EntitlementState.REVOKED,
                        revoked_at=NOW,
                        revocation_reason='chargeback',
                    )
                )
            else:
                await store.save_entitlement(build_entitlement())

        def handler(request: httpx.Request) -> httpx.Response:
            if mode == 'http_error':
                return httpx.Response(503, content=b'unavailable')
            if mode == 'transport_error':
                raise httpx.ConnectError('refused', request=request)
            if mode == 'digest_mismatch':
                return httpx.Response(200, content=b'wrong-bytes')
            return httpx.Response(200, content=PAYLOAD)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            service = DeliveryService(
                entitlements=store, entries=store, cache=cache, http=http
            )
            if mode == 'success':
                result = await service.deliver(BUYER_ID, CANDIDATE_ID)
                assert_no_origin_in_dump(result)
                return
            with pytest.raises(DeliveryRefusedError) as raised:
                await service.deliver(BUYER_ID, CANDIDATE_ID)
            assert_no_origin_in_error(raised.value)
