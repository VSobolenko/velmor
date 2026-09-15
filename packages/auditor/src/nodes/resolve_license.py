from __future__ import annotations

from packages.auditor.src.state import AuditorState
from packages.services.src.clock import Clock
from packages.services.src.domain.rights import Evidence, EvidenceKind
from packages.services.src.rights.license_matrix import LicenseMatrix


class ResolveLicenseNode:
    """Map the best available licence claim onto the policy table.

    Precedence is deliberate: a human ruling beats a model reading, which beats
    the source's own field. Each step down that list is less reliable than the one
    above it, and the evidence records which one was used.

    Resolving an identity is all this node does. Whether the resolved licence
    permits selling the good is the gate's decision, not this node's.
    """

    EXTRACTOR_VERSION = '1.0.0'

    def __init__(self, matrix: LicenseMatrix, clock: Clock) -> None:
        self._matrix = matrix
        self._clock = clock

    async def __call__(self, state: AuditorState) -> dict:
        claim = self._claim_from(state)
        grant = self._matrix.resolve(claim)

        if grant is None:
            return {'resolved_license_id': None}

        evidence = Evidence(
            kind=EvidenceKind.SPDX_MATCH,
            locator=f'item={state["candidate"].id}',
            excerpt=claim or '',
            retrieved_at=self._clock.now(),
            extractor_version=self.EXTRACTOR_VERSION,
        )
        return {
            'resolved_license_id': grant.license_id,
            'evidence': [*state['evidence'], evidence],
        }

    @staticmethod
    def _claim_from(state: AuditorState) -> str | None:
        ruling = state['human_ruling']
        if ruling is not None:
            return ruling.license_id if ruling.approved else None

        interpretation = state['interpretation']
        if interpretation is not None:
            return interpretation.license_claim

        return state['candidate'].declared_license_id
