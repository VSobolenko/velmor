"""Run one curation pass over the goods the shop has for sale.

Wired only here: the composition root is the one place allowed to choose the
curation model, the Saleor client, the cache and the store.
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from datetime import UTC, datetime

import httpx
import typer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.api.src.configs.settings import CommerceSettings
from packages.core.src.bootstrap.observability import Observability
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.services.src.commerce.category_service import CategoryService
from packages.services.src.commerce.curation import CatalogueCurator, CurationService
from packages.services.src.commerce.presentation_service import PresentationService
from packages.services.src.domain.curation import CurationOutcome, CurationRun
from packages.services.src.persistence.postgres import PostgresStore
from packages.services.src.saleor.client import SaleorClient


class CurationReport:
    """Write one curation run to the console, good by good.

    A good the run walked past is printed as itself rather than omitted. The
    question an operator asks after a run is "which goods still have no copy",
    and a report that only listed what it wrote could not answer it. A good that
    wrote no copy but named its category is stated as such, so a repair pass
    reads as the work it did rather than as a run that changed nothing.
    """

    def show(self, run: CurationRun) -> None:
        curated = self._count(run, True)
        typer.echo(f'curated {curated} of {len(run.outcomes)} catalogued goods')
        for outcome in run.outcomes:
            if outcome.wrote_presentation:
                typer.echo(
                    f'  curated   {outcome.candidate_id} -> {outcome.category_slug}'
                    f'{self._category_state(outcome)}'
                )
            elif outcome.filled_category_names:
                typer.echo(f'  names     {outcome.candidate_id} -> {outcome.category_slug}')
            else:
                typer.echo(f'  unchanged {outcome.candidate_id} [{outcome.category_slug}]')

    @staticmethod
    def _category_state(outcome: CurationOutcome) -> str:
        """Say whether the good's category was created or reused.

        The taxonomy stays usable only if a pass reuses it, so the report states
        which happened: a run that created a category per good reads differently
        from one that assigned every good to a category it already had.
        """
        if outcome.created_category:
            return ' (new category)'
        return ' (reused category)'

    @staticmethod
    def _count(run: CurationRun, wrote: bool) -> int:
        return sum(
            1 for outcome in run.outcomes if outcome.wrote_presentation is wrote
        )


class CurateCommand:
    """Propose and store shop copy and categories for the catalogue."""

    SERVICE_NAME = 'velmor-curate'
    DEFAULT_LIMIT = 200
    TIMEOUT_SECONDS = 120.0

    def __init__(self, loader: SettingsLoader) -> None:
        self._settings = CommerceSettings(loader)
        self._report = CurationReport()

    def run(self, model_name: str, limit: int, apply: bool) -> None:
        if not apply:
            typer.secho(
                'refused: pass --apply to store the proposals a curation run makes',
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        asyncio.run(self._run(model_name, limit))

    async def _run(self, model_name: str, limit: int) -> None:
        Observability(service_name=self.SERVICE_NAME).configure(self._settings)
        async with AsyncExitStack() as stack:
            http = await stack.enter_async_context(
                httpx.AsyncClient(
                    timeout=httpx.Timeout(self.TIMEOUT_SECONDS),
                    headers={'User-Agent': 'velmor/0.1 (+https://velmor.com)'},
                )
            )
            engine = create_async_engine(self._settings.database_dsn, pool_pre_ping=True)
            stack.push_async_callback(engine.dispose)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            store = PostgresStore(engine, session_factory)
            await store.ensure_schema()
            saleor = SaleorClient(
                http=http,
                api_url=self._settings.saleor_api_url,
                app_token=self._settings.saleor_app_token,
            )
            service = CurationService(
                catalog=store,
                candidates=store,
                presentations=PresentationService(store),
                categories=store,
                category_service=CategoryService(
                    categories=store, entries=store, saleor=saleor
                ),
                proposer=CatalogueCurator(model_name),
                clock=lambda: datetime.now(UTC),
            )
            self._report.show(await service.fill_missing(limit))
