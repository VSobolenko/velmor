from __future__ import annotations

import asyncio

from packages.services.src.connectors.factory import ConnectorFactory
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.query import SearchQuery
from packages.services.src.domain.scout_run import ScoutRun, SourceFailure
from packages.services.src.domain.source import SourceSpec
from packages.services.src.persistence.contract import CandidateRepository
from packages.services.src.sources.source_registry import SourceRegistry


class ScoutJob:
    """Deterministic discovery across every allowed source.

    Scout answers exactly one question: *what does each allowed source currently
    expose?* It reads a documented API, normalises the response, and stores it.
    There is no LLM and no judgement here, and that is deliberate: discovery is a
    high-frequency, low-risk operation, while the expensive reasoning belongs to
    the auditor. Nothing Scout does can publish anything.

    A source that fails is reported and skipped. One broken upstream never ends
    the run, and it never silently shrinks the funnel either.
    """

    def __init__(
        self,
        registry: SourceRegistry,
        factory: ConnectorFactory,
        repository: CandidateRepository,
    ) -> None:
        self._registry = registry
        self._factory = factory
        self._repository = repository

    async def run(self, query: SearchQuery, run_id: str) -> ScoutRun:
        specs = self._registry.enabled()
        outcomes = await asyncio.gather(
            *(self._discover(spec, query) for spec in specs),
            return_exceptions=True,
        )
        candidates, failures = self._partition(specs, outcomes)
        persisted = await self._repository.upsert_many(candidates)

        return ScoutRun(
            run_id=run_id,
            query=query.text,
            sources_queried=tuple(spec.id for spec in specs),
            discovered=len(candidates),
            persisted=persisted,
            failures=failures,
        )

    async def _discover(self, spec: SourceSpec, query: SearchQuery) -> tuple[Candidate, ...]:
        connector = self._factory.create(spec)
        return await connector.discover(query)

    def _partition(
        self,
        specs: tuple[SourceSpec, ...],
        outcomes: list[tuple[Candidate, ...] | BaseException],
    ) -> tuple[tuple[Candidate, ...], tuple[SourceFailure, ...]]:
        """Split gather's results into candidates and per-source failures.

        ``asyncio.gather(return_exceptions=True)`` returns a union of results and
        raised exceptions in positional order, so discriminating them here is
        reading the documented contract, not guessing at an unknown shape.
        """
        candidates: list[Candidate] = []
        failures: list[SourceFailure] = []

        for spec, outcome in zip(specs, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                failures.append(
                    SourceFailure(
                        source_id=spec.id,
                        reason=f'{type(outcome).__name__}: {outcome}',
                    )
                )
                continue
            candidates.extend(outcome)

        return tuple(candidates), tuple(failures)
