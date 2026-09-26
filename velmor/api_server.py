"""Serve the storefront over HTTP.

The server is wired here rather than through ``Container``: it runs no agent, so
it has no checkpoint store to open, no schema to create and no HTTP client of its
own to fetch pages with. It needs a store, delivery collaborators, payment
providers, checkout, and the catalogue query, and the composition root is the
one place allowed to decide that.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.api.src.app import ApiApplication
from packages.api.src.configs.settings import CommerceSettings
from packages.core.src.bootstrap.environment import Environment
from packages.core.src.bootstrap.observability import Observability
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.services.src.auth.service import AccountService
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.catalogue_service import StorefrontCatalogue
from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.commerce.preview import GoodPreview
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.protocol import PaymentProvider
from packages.services.src.payments.stripe_provider import StripeProvider
from packages.services.src.payments.stub_provider import StubPaymentProvider
from packages.services.src.persistence.postgres import PostgresStore


class ApiServer:
    """Run the storefront on the ASGI server."""

    DEFAULT_HOST = '127.0.0.1'
    DEFAULT_PORT = 8080
    SERVICE_NAME = 'velmor-api'

    def __init__(self, loader: SettingsLoader) -> None:
        self._settings: CommerceSettings = CommerceSettings(loader)

    def run(self, host: str, port: int) -> None:
        uvicorn.run(self._app(), host=host, port=port, log_level='info')

    def _app(self) -> FastAPI:
        Observability(service_name=self.SERVICE_NAME).configure(self._settings)
        engine = create_async_engine(self._settings.database_dsn, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PostgresStore(engine, session_factory)
        http = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={'User-Agent': 'velmor/0.1 (+https://velmor.com)'},
        )
        cache = AssetCache(
            root=self._settings.delivery_cache_dir,
            max_bytes=self._settings.delivery_cache_max_bytes,
        )
        delivery = DeliveryService(
            entitlements=store,
            entries=store,
            cache=cache,
            http=http,
        )
        grants = DeliveryGrantService(
            secret=self._settings.delivery_grant_secret,
            lifetime_seconds=self._settings.delivery_grant_lifetime_seconds,
        )
        stripe = StripeProvider(
            secret_key=self._settings.stripe_secret_key,
            webhook_secret=self._settings.stripe_webhook_signing_secret,
            http=http,
        )
        bepaid = BePaidProvider(
            shop_id=self._settings.bepaid_shop_id,
            secret_key=self._settings.bepaid_secret_key,
            public_key_pem=self._settings.bepaid_public_key,
            http=http,
            notification_url=self._settings.bepaid_notification_url,
        )
        providers: dict[str, PaymentProvider] = {'stripe': stripe, 'bepaid': bepaid}
        stub: StubPaymentProvider | None = None
        if self._settings.profile is Environment.DEV:
            stub = StubPaymentProvider(
                webhook_secret=self._settings.stub_webhook_secret,
            )
            providers[stub.provider_id] = stub
        checkout = CheckoutService(
            entries=store,
            disclosures=store,
            orders=store,
            entitlements=store,
            providers=providers,
        )
        catalogue = StorefrontCatalogue(
            catalog=store,
            entries=store,
            categories=store,
            candidates=store,
            covers=store,
            presentations=PresentationService(store),
            unit_amount=self._settings.catalogue_unit_amount,
            currency=self._settings.catalogue_currency,
        )
        preview = GoodPreview(
            entries=store,
            covers=store,
            cache=cache,
            http=http,
            derivative=PreviewDerivative(cache),
        )
        accounts = AccountService(
            accounts=store,
            sessions=store,
            clock=lambda: datetime.now(UTC),
            password_min_length=self._settings.password_min_length,
            failed_attempt_limit=self._settings.failed_attempt_limit,
            failed_attempt_window_seconds=self._settings.failed_attempt_window_seconds,
            session_lifetime_seconds=self._settings.session_lifetime_seconds,
        )

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            try:
                yield
            finally:
                await http.aclose()

        return ApiApplication(
            self._settings.environment,
            catalogue=catalogue,
            preview=preview,
            grants=grants,
            delivery=delivery,
            entitlements=store,
            clock=lambda: datetime.now(UTC),
            checkout=checkout,
            disclosures=store,
            stripe=stripe,
            bepaid=bepaid,
            orders=store,
            operator_refund_key=self._settings.operator_refund_key,
            storefront_domain=self._settings.storefront_domain,
            accounts=accounts,
            session_cookie_name=self._settings.session_cookie_name,
            session_lifetime_seconds=self._settings.session_lifetime_seconds,
            password_min_length=self._settings.password_min_length,
            stub=stub,
            lifespan=lifespan,
        ).build()
