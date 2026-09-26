"""Builders for the read services the HTTP surface is handed in tests.

``ApiApplication`` is constructed from the services that do the reading, not
from the repositories behind them, so every API test needs the same wiring.
Keeping it in one place means a change to a service constructor is one edit in
the tests rather than one per file.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

import httpx

from packages.services.src.auth.service import AccountService
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.catalogue_service import StorefrontCatalogue
from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.commerce.preview import GoodPreview
from packages.services.src.persistence.memory import InMemoryStore

#: The auth wiring every API test shares, so a service constructor change is one
#: edit here rather than one per harness.
TEST_SESSION_COOKIE_NAME = 'velmor_session'
TEST_SESSION_LIFETIME_SECONDS = 3600
TEST_PASSWORD_MIN_LENGTH = 10
TEST_FAILED_ATTEMPT_LIMIT = 5
TEST_FAILED_ATTEMPT_WINDOW_SECONDS = 900


def build_accounts(
    store: InMemoryStore,
    clock: Callable[[], datetime],
    *,
    password_min_length: int = TEST_PASSWORD_MIN_LENGTH,
    failed_attempt_limit: int = TEST_FAILED_ATTEMPT_LIMIT,
    failed_attempt_window_seconds: int = TEST_FAILED_ATTEMPT_WINDOW_SECONDS,
    session_lifetime_seconds: int = TEST_SESSION_LIFETIME_SECONDS,
) -> AccountService:
    """The account service over the same in-memory store the API writes."""
    return AccountService(
        accounts=store,
        sessions=store,
        clock=clock,
        password_min_length=password_min_length,
        failed_attempt_limit=failed_attempt_limit,
        failed_attempt_window_seconds=failed_attempt_window_seconds,
        session_lifetime_seconds=session_lifetime_seconds,
    )


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
