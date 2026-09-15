from __future__ import annotations

from abc import ABC, abstractmethod

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.query import SearchQuery
from packages.services.src.domain.source import SourceSpec


class SourceConnector(ABC):
    """Read-only adapter over one source's discovery API.

    A connector does exactly one thing: turn a query into candidates. It does not
    filter by license, decide publishability, or write anything. Rights decisions
    belong to the rights engine and the publication gate, which every candidate
    must pass regardless of where it came from.

    Implementations must set ``declared_license_id`` from the source's own
    machine-readable field whenever the source reports one. That field is the
    provenance the auditor later cites, so leaving it empty silently downgrades a
    tier A source into an unverifiable one.
    """

    def __init__(self, spec: SourceSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> SourceSpec:
        return self._spec

    @abstractmethod
    async def discover(self, query: SearchQuery) -> tuple[Candidate, ...]:
        """Return at most ``query.limit`` candidates for the given query."""
