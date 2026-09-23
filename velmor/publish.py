"""Run the publication bridge over gate-publishable goods.

Wired only here: the composition root is the one place allowed to choose
``CommerceSettings``, the Saleor client, the digest path and the store.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import AsyncExitStack
from datetime import UTC, datetime

import httpx
import typer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.api.src.configs.settings import CommerceSettings
from packages.core.src.bootstrap.observability import Observability
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.digest import ContentDigest
from packages.services.src.commerce.publication import PublicationBridge
from packages.services.src.domain.publication import PublicationAction, PublicationOutcome
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.persistence.postgres import PostgresStore
from packages.services.src.rights.license_grants import DefaultLicenseGrants
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.src.rights.rights_resolver import RightsResolver
from packages.services.src.saleor.client import SaleorClient
from packages.services.src.sources.source_registry import DefaultSources, SourceRegistry


class PublishCommand:
    """Push gate-publishable goods into Saleor and the paid catalogue."""

    SERVICE_NAME = 'velmor-publish'
    DEFAULT_LIMIT = 200

    def __init__(self, loader: SettingsLoader) -> None:
        self._settings = CommerceSettings(loader)
        self._registry = SourceRegistry(DefaultSources.TABLE, loader)

    def run(self, limit: int) -> None:
        asyncio.run(self._run(limit))

    async def _run(self, limit: int) -> None:
        Observability(service_name=self.SERVICE_NAME).configure(self._settings)
        async with AsyncExitStack() as stack:
            http = await stack.enter_async_context(
                httpx.AsyncClient(
                    timeout=httpx.Timeout(60.0),
                    headers={'User-Agent': 'velmor/0.1 (+https://velmor.com)'},
                )
            )
            engine = create_async_engine(self._settings.database_dsn, pool_pre_ping=True)
            stack.push_async_callback(engine.dispose)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            store = PostgresStore(engine, session_factory)
            await store.ensure_schema()

            cache = AssetCache(
                root=self._settings.delivery_cache_dir,
                max_bytes=self._settings.delivery_cache_max_bytes,
            )
            digest = ContentDigest(http=http, cache=cache)
            saleor = SaleorClient(
                http=http,
                api_url=self._settings.saleor_api_url,
                app_token=self._settings.saleor_app_token,
            )
            gate = PublicationGate(LicenseMatrix(DefaultLicenseGrants.TABLE))
            bridge = PublicationBridge(
                gate=gate,
                saleor=saleor,
                entries=store,
                categories=store,
                digest=digest,
            )
            await self._publish_all(store, bridge, gate, limit)

    async def _publish_all(
        self,
        store: PostgresStore,
        bridge: PublicationBridge,
        gate: PublicationGate,
        limit: int,
    ) -> None:
        pairs = await store.published(limit)
        counts: Counter[PublicationAction] = Counter()
        now = datetime.now(UTC)
        for candidate, record in pairs:
            spec = self._registry.by_id(candidate.source_id)
            decision = gate.decide(spec, record)
            outcome = await bridge.apply(candidate, decision, spec, now)
            reported = self._with_engine_version_reason(outcome, record)
            counts[reported.action] += 1
            self._log_outcome(candidate.id, reported.action, reported.reasons)
        self._log_summary(len(pairs), counts)

    def _with_engine_version_reason(
        self, outcome: PublicationOutcome, record: RightsRecord
    ) -> PublicationOutcome:
        """Report a ruling recorded under an engine other than the running one.

        The mismatch is a reason on the outcome, never a refusal: every record on
        sale today predates the running engine, so refusing would withdraw the
        catalogue for a divergence only a re-decision could act on. The action is
        the one the ruling produces either way.
        """
        if record.engine_version == RightsResolver.ENGINE_VERSION:
            return outcome
        reason = (
            f'ruling was recorded by engine {record.engine_version}; '
            f'the running engine is {RightsResolver.ENGINE_VERSION}'
        )
        return PublicationOutcome(
            candidate_id=outcome.candidate_id,
            action=outcome.action,
            reasons=(*outcome.reasons, reason),
            entry=outcome.entry,
        )

    def _log_outcome(
        self,
        candidate_id: str,
        action: PublicationAction,
        reasons: tuple[str, ...],
    ) -> None:
        detail = f': {"; ".join(reasons)}' if reasons else ''
        typer.echo(f'{action.value:<10} {candidate_id}{detail}')

    def _log_summary(self, total: int, counts: Counter[PublicationAction]) -> None:
        typer.echo(f'processed {total}')
        for action in PublicationAction:
            typer.echo(f'  {action.value}: {counts[action]}')
