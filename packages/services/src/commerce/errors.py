from __future__ import annotations

from packages.core.src.errors import VelmorError


class PublicationSourceMismatchError(VelmorError):
    """The candidate or decision names a source other than the one supplied."""
