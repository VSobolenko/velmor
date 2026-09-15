from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class CredentialSource(Protocol):
    """Presence check over configured credentials.

    Deliberately narrower than the settings loader: the source registry only ever
    asks whether a key was supplied, so tests can supply a plain stub instead of
    writing a real ``.env`` file to disk.
    """

    @property
    def env_file(self) -> Path: ...

    def has(self, key: str) -> bool: ...
