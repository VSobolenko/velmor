from __future__ import annotations

from packages.auditor.src.state import AuditorState
from packages.services.src.clock import Clock
from packages.services.src.domain.rights import Evidence, EvidenceKind
from packages.services.src.domain.source import SourceTier


class CollectDeclaredEvidenceNode:
    """Turn the source's own machine-readable licence field into evidence.

    Only a tier A source produces this. A tier B source exposes rights prose that
    needs interpreting, so pretending its field was machine-readable would let an
    interpretation masquerade as an observation and slip past the gate.
    """

    EXTRACTOR_VERSION = '1.0.0'

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    async def __call__(self, state: AuditorState) -> dict:
        source = state['source']
        candidate = state['candidate']
        declared = candidate.declared_license_id

        if declared is None or source.tier is not SourceTier.A:
            return {}

        evidence = Evidence(
            kind=EvidenceKind.SOURCE_API_FIELD,
            locator=f'{source.base_url} item={candidate.id}',
            excerpt=declared,
            retrieved_at=self._clock.now(),
            extractor_version=self.EXTRACTOR_VERSION,
        )
        return {'evidence': [*state['evidence'], evidence]}
