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


class DigestUnavailableError(VelmorError):
    """The origin digest could not be obtained; publication must refuse."""


class AssetCacheError(VelmorError):
    """The small-file cache refused or could not complete an operation."""


class DeliveryRefusedError(VelmorError):
    """Delivery refused; the message is safe to show a buyer (no origin URL)."""


class GrantRefusedError(VelmorError):
    """A delivery grant was refused; the message must not leak the secret or token."""


class CheckoutRefusedError(VelmorError):
    """Checkout refused payment; the message names the good or missing disclosure."""


class PreviewNotFoundError(VelmorError):
    """No preview exists for this good: unknown, withdrawn, or not decodable.

    One error for the three cases on purpose. The buyer's page shows its own
    placeholder whichever it is, and telling a caller apart "no such good" from
    "not an image" would describe the origin, which concealment forbids.
    """


class PreviewDigestMismatchError(VelmorError):
    """Origin bytes no longer match the digest recorded at publication."""


class PreviewOriginUnreachableError(VelmorError):
    """The origin could not be reached; the message must not name it."""


class PreviewCoverMissingError(VelmorError):
    """A cover is recorded for a good but its bytes are not in the asset cache."""


class CoverRefusedError(VelmorError):
    """A cover was refused: the good is not catalogued, or no permission is recorded."""


class CurationRefusedError(VelmorError):
    """A curation run could not store what it proposed."""
