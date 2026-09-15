from __future__ import annotations

from collections.abc import Callable

import httpx

from packages.core.src.errors import SourceContractError
from packages.services.src.connectors.contract import SourceConnector
from packages.services.src.connectors.openverse import OpenverseConnector
from packages.services.src.domain.source import SourceSpec


class ConnectorFactory:
    """Map a registered source to the connector that can crawl it.

    A source whose connector has not been written yet is refused loudly rather
    than skipped quietly. The source registry marks such sources disabled, so
    reaching this error means the two lists have drifted apart.
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http
        self._builders: dict[str, Callable[[SourceSpec], SourceConnector]] = {
            'openverse': lambda spec: OpenverseConnector(spec, self._http),
        }

    def create(self, spec: SourceSpec) -> SourceConnector:
        builder = self._builders.get(spec.id)
        if builder is None:
            raise SourceContractError(
                f'No connector is implemented for source {spec.id!r}. '
                f'Implemented: {", ".join(sorted(self._builders))}. '
                f'Either implement the connector or set enabled=False on the source spec.'
            )
        return builder(spec)

    def implemented_source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._builders))
