from __future__ import annotations

from contextlib import AsyncExitStack

import httpx
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from packages.core.src.bootstrap.observability import Observability
from packages.core.src.bootstrap.platform_settings import PlatformSettings
from packages.services.src.clock import SystemClock
from packages.services.src.persistence.contract import CandidateRepository, RightsRecordRepository
from packages.services.src.persistence.postgres import PostgresStore
from packages.services.src.rights.engine import RightsEngine
from packages.services.src.rights.license_grants import DefaultLicenseGrants
from packages.services.src.screening.prohibited_screen import ProhibitedCategoryScreen
from packages.services.src.sources.source_registry import DefaultSources, SourceRegistry


class Container:
    """The composition root: the only place that chooses concrete implementations.

    Wiring is explicit rather than mediated by a dependency-injection framework.
    Every dependency is a plain constructor argument, so reading this file is
    enough to learn what a process is made of, and a test can build any subset of
    it without learning a container DSL.

    Objects with no lifecycle are built in ``__init__`` and shared. Anything
    holding a network resource is opened in ``__aenter__`` and released by the
    exit stack in ``__aexit__``, including resources opened later on demand.
    """

    def __init__(self, settings: PlatformSettings, service_name: str) -> None:
        self.settings = settings
        self.observability = Observability(service_name=service_name)
        self.clock = SystemClock()
        self.engine = RightsEngine(DefaultLicenseGrants.TABLE)
        self.registry = SourceRegistry(DefaultSources.TABLE, settings.loader)
        self.screen = ProhibitedCategoryScreen()
        self._stack: AsyncExitStack | None = None
        self._http: httpx.AsyncClient | None = None
        self._db_engine: AsyncEngine | None = None
        self._store: PostgresStore | None = None
        self._checkpointer: BaseCheckpointSaver | None = None

    async def __aenter__(self) -> Container:
        self.observability.configure(self.settings)

        # Fail here, not mid-crawl, when an enabled source lacks credentials.
        self.registry.validate_credentials()

        self._stack = AsyncExitStack()
        self._http = await self._stack.enter_async_context(
            httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={'User-Agent': 'velmor/0.1 (+https://velmor.com)'},
            )
        )

        self._db_engine = create_async_engine(self.settings.database_dsn, pool_pre_ping=True)
        self._stack.push_async_callback(self._db_engine.dispose)

        session_factory = async_sessionmaker(self._db_engine, expire_on_commit=False)
        self._store = PostgresStore(self._db_engine, session_factory)
        await self._store.ensure_schema()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._http = None
        self._db_engine = None
        self._store = None
        self._checkpointer = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError('Container is not entered: use "async with Container(...)"')
        return self._http

    async def candidate_repository(self) -> CandidateRepository:
        return self._require_store()

    async def verdict_repository(self) -> RightsRecordRepository:
        return self._require_store()

    async def checkpointer(self) -> BaseCheckpointSaver:
        """Open the durable checkpoint store, once per container.

        Only the verification graph needs this. Discovery has no state worth
        keeping across a restart, so opening a checkpoint store for it would cost
        writes for nothing.
        """
        if self._checkpointer is not None:
            return self._checkpointer
        if self._stack is None:
            raise RuntimeError('Container is not entered: use "async with Container(...)"')

        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver = await self._stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(self._checkpoint_dsn())
        )
        await saver.setup()
        self._checkpointer = saver
        return saver

    def _checkpoint_dsn(self) -> str:
        """Address the checkpoint store in libpq form.

        The store is reached through SQLAlchemy, which needs the driver suffix
        in ``postgresql+asyncpg://``; the saver parses the same string with
        libpq and rejects that suffix. Both point at one database, so the DSN is
        derived here rather than duplicated in the environment.
        """
        url = make_url(self.settings.database_dsn)
        return url.set(drivername='postgresql').render_as_string(hide_password=False)

    def _require_store(self) -> PostgresStore:
        if self._store is None:
            raise RuntimeError('Container is not entered: use "async with Container(...)"')
        return self._store
