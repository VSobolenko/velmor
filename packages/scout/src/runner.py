from __future__ import annotations

import asyncio
import uuid

from packages.scout.src.ingest import ScoutJob
from packages.services.src.domain.query import SearchQuery
from packages.services.src.domain.scout_run import ScoutRun


class ScoutRunner:
    """Run discovery passes on an interval.

    ``run_once`` is separated from ``run`` so a pass can be executed and asserted
    on directly, without a test having to own an infinite loop.
    """

    def __init__(
        self,
        job: ScoutJob,
        queries: tuple[str, ...],
        page_limit: int,
        interval_seconds: int,
    ) -> None:
        self._job = job
        self._queries = queries
        self._page_limit = page_limit
        self._interval_seconds = interval_seconds

    async def run(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(self._interval_seconds)

    async def run_once(self) -> tuple[ScoutRun, ...]:
        runs = []
        for text in self._queries:
            query = SearchQuery(text=text, limit=self._page_limit)
            runs.append(await self._job.run(query, run_id=str(uuid.uuid4())))
        return tuple(runs)
