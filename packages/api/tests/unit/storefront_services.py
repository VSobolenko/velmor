"""Builders for the read services the HTTP surface is handed in tests.

``ApiApplication`` is constructed from the services that do the reading, not
from the repositories behind them, so every API test needs the same wiring.
Keeping it in one place means a change to a service constructor is one edit in
the tests rather than one per file.
"""

from __future__ import annotations

from decimal import Decimal

import httpx

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.catalogue_service import StorefrontCatalogue
from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.commerce.preview import GoodPreview
from packages.services.src.persistence.memory import InMemoryStore


def build_catalogue(
    store: InMemoryStore,
    unit_amount: Decimal,
    currency: str,
) -> StorefrontCatalogue:
    """The buyer's read path over an in-memory store."""
    return StorefrontCatalogue(
        catalog=store,
        entries=store,
        categories=store,
        candidates=store,
        covers=store,
        presentations=PresentationService(store),
        unit_amount=unit_amount,
        currency=currency,
    )


def build_preview(
    store: InMemoryStore,
    cache: AssetCache,
    http: httpx.AsyncClient,
) -> GoodPreview:
    """The preview path over an in-memory store and a test cache."""
    return GoodPreview(
        entries=store,
        covers=store,
        cache=cache,
        http=http,
        derivative=PreviewDerivative(cache),
    )
