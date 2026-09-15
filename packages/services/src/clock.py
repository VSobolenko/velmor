from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Time as an injectable dependency.

    Every deterministic decision is stamped with the moment it was made, so a
    test can assert on an exact timestamp instead of a range.
    """

    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
