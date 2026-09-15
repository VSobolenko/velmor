from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from packages.services.src.domain.rights import RightsAction


class StorefrontListing(StrEnum):
    """Whether a license family may appear in the paid catalog at all.

    Separate from "is commercial use allowed". Copyleft licenses allow
    commercial use, but a buyer who may freely redistribute what they bought
    voids the price, so those goods are not listed for sale.
    """

    PAID_OK = 'paid_ok'
    FREE_ONLY = 'free_only'
    NOT_LISTED = 'not_listed'


class LicenseGrant(BaseModel):
    """What one license family permits, as platform policy.

    This is a policy table, not a lawyer's opinion. Every entry states the
    actions the platform is willing to treat as granted; an unknown license is
    denied, never guessed.
    """

    model_config = {'frozen': True}

    license_id: str
    name: str
    granted_actions: tuple[RightsAction, ...]
    obligations: tuple[str, ...]
    commercial_use_allowed: bool
    modification_allowed: bool
    storefront_listing: StorefrontListing
