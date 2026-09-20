from __future__ import annotations

from packages.core.src.errors import VelmorError


class PublicationSourceMismatchError(VelmorError):
    """The candidate or decision names a source other than the one supplied."""


class CategorySlugTakenError(VelmorError):
    """Create or rename would collide on an existing category slug."""


class CategoryNotFoundError(VelmorError):
    """The category id is not in the store."""


class CategoryNotEmptyError(VelmorError):
    """Remove refused because the category still holds catalogue entries."""

    def __init__(self, message: str, blocking_candidate_ids: tuple[str, ...]) -> None:
        super().__init__(message)
        self.blocking_candidate_ids = blocking_candidate_ids


class CatalogueEntryNotFoundError(VelmorError):
    """Assign or unassign targeted a candidate with no catalogue entry."""


class CatalogueEntryNotPublishedError(VelmorError):
    """Assign or unassign targeted an entry that is not PUBLISHED."""
