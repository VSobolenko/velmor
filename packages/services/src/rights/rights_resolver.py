from __future__ import annotations

from datetime import datetime

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.rights import (
    Evidence,
    RightsAction,
    RightsRecord,
    RightsVerdict,
)
from packages.services.src.rights.license_matrix import LicenseMatrix


class RightsResolver:
    """Decide what a license permits for a candidate.

    This answers one question only: *does the declared license grant the actions
    the platform intends to take?* It deliberately says nothing about whether the
    declared license has been proven. Proving it is the publication gate's job,
    and keeping the two apart is what makes a verdict auditable.

    An unrecognised or absent license resolves to ``UNKNOWN``. It is never
    treated as permissive.
    """

    ENGINE_VERSION: str = '1.1.0'
    """Version of the rights decision as a whole, resolver and gate together.

    Stamped into every ``RightsRecord``, and reachable from a ``GateDecision``
    through the record it carries, so a publication ruling is always attributable
    to the policy that produced it. It lives here because this module is the leaf
    that both the resolver and the gate can import without a cycle.

    1.1.0 tightened the gate: evidence now has to come from the source, so
    records that previously published on an interpreted identity are refused.
    """

    def __init__(self, matrix: LicenseMatrix) -> None:
        self._matrix = matrix

    def resolve(
        self,
        candidate: Candidate,
        requested_actions: tuple[RightsAction, ...],
        evidence: tuple[Evidence, ...],
        decided_at: datetime,
    ) -> RightsRecord:
        grant = self._matrix.resolve(candidate.declared_license_id)

        if grant is None:
            return self._unknown(candidate, requested_actions, evidence, decided_at)

        missing = tuple(
            action for action in requested_actions if action not in grant.granted_actions
        )

        if missing:
            return self._denied(
                candidate, requested_actions, evidence, decided_at, grant.license_id, missing
            )

        return RightsRecord(
            candidate_id=candidate.id,
            source_id=candidate.source_id,
            license_id=grant.license_id,
            requested_actions=requested_actions,
            verdict=RightsVerdict.ALLOWED,
            granted_actions=grant.granted_actions,
            obligations=grant.obligations,
            evidence=evidence,
            reason=f'{grant.name} grants every requested action',
            engine_version=self.ENGINE_VERSION,
            decided_at=decided_at,
        )

    def _unknown(
        self,
        candidate: Candidate,
        requested_actions: tuple[RightsAction, ...],
        evidence: tuple[Evidence, ...],
        decided_at: datetime,
    ) -> RightsRecord:
        declared = candidate.declared_license_id
        reason = (
            'Candidate declares no license'
            if declared is None
            else f'License {declared!r} does not map to any license Velmor knows'
        )
        return RightsRecord(
            candidate_id=candidate.id,
            source_id=candidate.source_id,
            license_id=None,
            requested_actions=requested_actions,
            verdict=RightsVerdict.UNKNOWN,
            granted_actions=(),
            obligations=(),
            evidence=evidence,
            reason=reason,
            engine_version=self.ENGINE_VERSION,
            decided_at=decided_at,
        )

    def _denied(
        self,
        candidate: Candidate,
        requested_actions: tuple[RightsAction, ...],
        evidence: tuple[Evidence, ...],
        decided_at: datetime,
        license_id: str,
        missing: tuple[RightsAction, ...],
    ) -> RightsRecord:
        grant = self._matrix.resolve(license_id)
        missing_names = ', '.join(action.value for action in missing)
        granted = grant.granted_actions if grant is not None else ()
        return RightsRecord(
            candidate_id=candidate.id,
            source_id=candidate.source_id,
            license_id=license_id,
            requested_actions=requested_actions,
            verdict=RightsVerdict.DENIED,
            granted_actions=granted,
            obligations=grant.obligations if grant is not None else (),
            evidence=evidence,
            reason=f'{license_id} does not grant: {missing_names}',
            engine_version=self.ENGINE_VERSION,
            decided_at=decided_at,
        )
