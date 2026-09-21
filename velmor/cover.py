"""Attach and list the covers shown for goods that have no image of their own.

Wired only here: the composition root is the one place allowed to choose the
delivery cache and the store.
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path

import typer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.api.src.configs.settings import CommerceSettings
from packages.core.src.bootstrap.observability import Observability
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.covers import CoverAttacher
from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.domain.preview import CoverSource
from packages.services.src.persistence.postgres import PostgresStore


class CoverCommand:
    """Attach a cover to a good, and list the covers already attached."""

    SERVICE_NAME = 'velmor-cover'

    def __init__(self, loader: SettingsLoader) -> None:
        self._settings = CommerceSettings(loader)

    def attach(
        self,
        candidate_id: str,
        path: Path,
        source: CoverSource,
        rights_note: str,
    ) -> None:
        asyncio.run(self._attach(candidate_id, path, source, rights_note))

    def list(self) -> None:
        asyncio.run(self._list())

    async def _attach(
        self,
        candidate_id: str,
        path: Path,
        source: CoverSource,
        rights_note: str,
    ) -> None:
        async with AsyncExitStack() as stack:
            store = await self._open_store(stack)
            cover = await self._attacher(store).attach(
                candidate_id, path, source, rights_note
            )
            typer.echo(
                f'attached {cover.source.value} cover for {cover.candidate_id} '
                f'({cover.media_type})'
            )

    async def _list(self) -> None:
        async with AsyncExitStack() as stack:
            store = await self._open_store(stack)
            covers = await self._attacher(store).attached()
            typer.echo(f'{len(covers)} covers attached')
            for cover in covers:
                typer.echo(f'  {cover.candidate_id} {cover.source.value} {cover.media_type}')

    async def _open_store(self, stack: AsyncExitStack) -> PostgresStore:
        Observability(service_name=self.SERVICE_NAME).configure(self._settings)
        engine = create_async_engine(self._settings.database_dsn, pool_pre_ping=True)
        stack.push_async_callback(engine.dispose)
        store = PostgresStore(engine, async_sessionmaker(engine, expire_on_commit=False))
        await store.ensure_schema()
        return store

    def _attacher(self, store: PostgresStore) -> CoverAttacher:
        cache = AssetCache(
            root=self._settings.delivery_cache_dir,
            max_bytes=self._settings.delivery_cache_max_bytes,
        )
        return CoverAttacher(
            entries=store,
            covers=store,
            derivative=PreviewDerivative(cache),
            clock=lambda: datetime.now(UTC),
        )
