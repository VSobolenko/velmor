from __future__ import annotations

import tempfile
from pathlib import Path

from packages.services.src.commerce.errors import AssetCacheError


class AssetCache:
    """Small-file cache keyed by content digest under a configured root."""

    def __init__(self, root: Path, max_bytes: int) -> None:
        self._root = root
        self.max_bytes = max_bytes

    def put(self, digest: str, data: bytes) -> None:
        if len(data) > self.max_bytes:
            raise AssetCacheError(
                f'payload of {len(data)} bytes exceeds cache max of {self.max_bytes}'
            )
        self._root.mkdir(parents=True, exist_ok=True)
        destination = self._path_for(digest)
        with tempfile.NamedTemporaryFile(dir=self._root, delete=False) as handle:
            handle.write(data)
            temp_name = handle.name
        Path(temp_name).replace(destination)

    def get(self, digest: str) -> bytes | None:
        path = self._path_for(digest)
        if not path.is_file():
            return None
        return path.read_bytes()

    def has(self, digest: str) -> bool:
        return self._path_for(digest).is_file()

    def scoped(self, name: str) -> AssetCache:
        """A cache over ``<root>/<name>``, sharing this cache's size budget.

        Used for a derivative that must not be confusable with an origin file
        of the same digest, while still living under the one delivery cache the
        process is configured with.
        """
        return AssetCache(root=self._root / name, max_bytes=self.max_bytes)

    def _path_for(self, digest: str) -> Path:
        return self._root / f'{digest}.bin'
