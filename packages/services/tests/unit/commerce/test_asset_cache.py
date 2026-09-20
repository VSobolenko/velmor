from __future__ import annotations

from pathlib import Path

import pytest

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.errors import AssetCacheError

DIGEST = 'ab' * 32
PAYLOAD = b'hello-cache'


class TestAssetCache:
    def test_put_then_get_returns_the_same_bytes(self, tmp_path: Path) -> None:
        cache = AssetCache(root=tmp_path, max_bytes=1024)

        cache.put(DIGEST, PAYLOAD)

        assert cache.get(DIGEST) == PAYLOAD
        assert cache.has(DIGEST) is True
        assert (tmp_path / f'{DIGEST}.bin').is_file()

    def test_get_unknown_digest_returns_none(self, tmp_path: Path) -> None:
        cache = AssetCache(root=tmp_path, max_bytes=1024)

        assert cache.get('00' * 32) is None
        assert cache.has('00' * 32) is False

    def test_put_refuses_oversized_payload(self, tmp_path: Path) -> None:
        cache = AssetCache(root=tmp_path, max_bytes=4)
        oversized = b'12345'

        with pytest.raises(AssetCacheError):
            cache.put(DIGEST, oversized)

        assert cache.get(DIGEST) is None
        assert list(tmp_path.iterdir()) == []

    def test_put_creates_root_when_missing(self, tmp_path: Path) -> None:
        root = tmp_path / 'nested' / 'cache'
        cache = AssetCache(root=root, max_bytes=1024)

        cache.put(DIGEST, PAYLOAD)

        assert root.is_dir()
        assert cache.get(DIGEST) == PAYLOAD

    def test_put_overwrites_existing(self, tmp_path: Path) -> None:
        cache = AssetCache(root=tmp_path, max_bytes=1024)
        cache.put(DIGEST, b'first')
        cache.put(DIGEST, b'second')

        assert cache.get(DIGEST) == b'second'
