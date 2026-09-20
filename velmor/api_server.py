"""Serve the storefront over HTTP.

The server is wired here rather than through ``Container``: it runs no agent, so
it has no checkpoint store to open, no schema to create and no HTTP client of its
own to fetch pages with. It needs a store and the catalogue query, and nothing
else, and the composition root is the one place allowed to decide that.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.api.src.app import ApiApplication
from packages.api.src.configs.settings import CommerceSettings
from packages.core.src.bootstrap.observability import Observability
from packages.core.src.bootstrap.settings_loader import SettingsLoader
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
        return ApiApplication(self._settings.environment, store).build()
