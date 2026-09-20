from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.digest import DIGEST_ALGORITHM, ContentDigest
from packages.services.src.commerce.errors import DigestUnavailableError


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestContentDigest:
    async def test_successful_digest_under_threshold_is_cached(self, tmp_path: Path) -> None:
        body = b'known-asset-bytes'
        expected = hashlib.sha256(body).hexdigest()

        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == 'https://origin.test/file.bin'
            return httpx.Response(200, content=body)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            digest = ContentDigest(http=http, cache=cache)
            result = await digest.obtain('https://origin.test/file.bin')

        assert DIGEST_ALGORITHM == 'sha256'
        assert result.digest == expected
        assert result.size_bytes == len(body)
        assert result.cached is True
        assert cache.get(expected) == body

    async def test_http_error_status_raises_and_writes_nothing(self, tmp_path: Path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b'gone')

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            digest = ContentDigest(http=http, cache=cache)
            with pytest.raises(DigestUnavailableError) as raised:
                await digest.obtain('https://origin.test/missing.bin')

        assert '404' in str(raised.value)
        assert list(tmp_path.iterdir()) == []

    async def test_transport_failure_raises_with_cause(self, tmp_path: Path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError('refused', request=request)

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            digest = ContentDigest(http=http, cache=cache)
            with pytest.raises(DigestUnavailableError) as raised:
                await digest.obtain('https://origin.test/file.bin')

        assert raised.value.__cause__ is not None
        assert isinstance(raised.value.__cause__, httpx.ConnectError)
        assert list(tmp_path.iterdir()) == []

    async def test_body_over_threshold_is_not_cached(self, tmp_path: Path) -> None:
        body = b'x' * 20
        expected = hashlib.sha256(body).hexdigest()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body)

        cache = AssetCache(root=tmp_path, max_bytes=10)
        async with _client(handler) as http:
            digest = ContentDigest(http=http, cache=cache)
            result = await digest.obtain('https://origin.test/large.bin')

        assert result.digest == expected
        assert result.size_bytes == 20
        assert result.cached is False
        assert cache.get(expected) is None

    async def test_blank_url_raises_without_http(self, tmp_path: Path) -> None:
        called = False

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal called
            called = True
            return httpx.Response(200, content=b'x')

        cache = AssetCache(root=tmp_path, max_bytes=1024)
        async with _client(handler) as http:
            digest = ContentDigest(http=http, cache=cache)
            with pytest.raises(DigestUnavailableError):
                await digest.obtain('   ')

        assert called is False
