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

    This answers one question only: *does the claimed license grant the actions
    the platform intends to take?* It deliberately says nothing about whether the
    claimed license has been proven, nor about where the claim came from. Proving
    it is the publication gate's job, and keeping the two apart is what makes a
    verdict auditable.

    The claim is an explicit argument rather than a field read off the candidate.
    Which claim applies is settled by whoever accumulated the evidence - a human
    ruling over a model reading over the source's own field - and the resolver
    receives the outcome of that. Reading ``candidate.declared_license_id`` here
    instead would discard a ruling a person had already made, and would decide on
    the source's field while the record's evidence attested a license the source
    never declared.

    An unrecognised or absent license resolves to ``UNKNOWN``. It is never
    treated as permissive.
    """

    ENGINE_VERSION: str = '1.2.0'
    """Version of the rights decision as a whole, resolver and gate together.

    Stamped into every ``RightsRecord``, and reachable from a ``GateDecision``
    through the record it carries, so a publication ruling is always attributable
    to the policy that produced it. It lives here because this module is the leaf
    that both the resolver and the gate can import without a cycle.

    1.1.0 tightened the gate: evidence now has to come from the source, so
    records that previously published on an interpreted identity are refused.

    1.2.0 makes the decision follow the license claim the run established. A
    human ruling and an investigated page now reach the verdict, and a record can
    no longer be refused for the source's declared field while its evidence
    attests a different license.
    """

    def __init__(self, matrix: LicenseMatrix) -> None:
        self._matrix = matrix

    def resolve(
        self,
        candidate: Candidate,
        license_claim: str | None,
        requested_actions: tuple[RightsAction, ...],
        evidence: tuple[Evidence, ...],
        decided_at: datetime,
    ) -> RightsRecord:
        grant = self._matrix.resolve(license_claim)

        if grant is None:
            return self._unknown(candidate, license_claim, requested_actions, evidence, decided_at)

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
        license_claim: str | None,
        requested_actions: tuple[RightsAction, ...],
        evidence: tuple[Evidence, ...],
        decided_at: datetime,
    ) -> RightsRecord:
        reason = (
            'Candidate declares no license'
            if license_claim is None
            else f'License {license_claim!r} does not map to any license Velmor knows'
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
