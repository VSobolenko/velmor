from __future__ import annotations

from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.rights import Evidence, EvidenceKind, RightsRecord, RightsVerdict
from packages.services.src.domain.source import SourceSpec, SourceTier
from packages.services.src.rights.license_matrix import LicenseMatrix


class PublicationGate:
    """The single place allowed to say "publish this".

    Deny by default. A good reaches the catalog only when every condition below
    is provably satisfied; anything else is discarded rather than queued. That
    strictness is the safety mechanism, and its cost is catalog size.

    The gate never repairs a weak record. If the evidence is incomplete it
    rejects and explains, so the reason is visible to whoever asks why a good is
    missing from the storefront.

    Evidence counts only when it came from the source. ``SOURCE_EVIDENCE_KINDS``
    is an allowlist of those kinds, and an identity match is required on top of
    it. A model reading is not on that list: the licence string a model proposes
    would otherwise be laundered into a declared fact by the matcher that
    normalises it, and the record would look as though it rested on the source. A
    human attestation is accepted, because a person taking responsibility for a
    licence identity is the strongest signal the platform has, and that is safe
    precisely because the human cannot override policy: they resolve *which*
    licence applies, while the matrix still decides what that licence permits and
    whether it may be listed.
    """

    SOURCE_EVIDENCE_KINDS: tuple[EvidenceKind, ...] = (
        EvidenceKind.SOURCE_API_FIELD,
        EvidenceKind.LICENSE_FILE,
        EvidenceKind.HUMAN_ATTESTATION,
    )
    """Kinds that count as a fact obtained from the source.

    An allowlist rather than a denylist, and that choice is the safety property:
    a newly added ``EvidenceKind`` is untrusted until it is named here. A
    denylist would make every future kind trusted by default, which is
    allow-by-default logic inside an engine whose whole premise is deny by
    default.

    ``SPDX_MATCH`` is deliberately absent. It records that an identity was
    matched against a known licence, and the string that was matched can have
    come from a model reading a page. Trusting it as source evidence is what
    turned an interpretation into an apparent declaration. It still does its own
    job below: proving that identity matching happened at all.
    """

    def __init__(self, matrix: LicenseMatrix) -> None:
        self._matrix = matrix

    def decide(self, spec: SourceSpec, record: RightsRecord) -> GateDecision:
        reasons: list[str] = []

        self._check_source(spec, reasons)
        self._check_verdict(record, reasons)
        self._check_identity(record, reasons)
        self._check_evidence(record, reasons)

        return GateDecision(
            candidate_id=record.candidate_id,
            publishable=not reasons,
            reasons=tuple(reasons),
            record=record,
        )

    def listing_for(self, record: RightsRecord) -> StorefrontListing:
        """Where a publishable good belongs, or that it belongs nowhere."""
        grant = self._matrix.resolve(record.license_id)
        if grant is None:
            return StorefrontListing.NOT_LISTED
        return grant.storefront_listing

    def _check_source(self, spec: SourceSpec, reasons: list[str]) -> None:
        if spec.tier is SourceTier.C:
            reasons.append(
                f'Source {spec.id!r} is tier C: its rights are not machine-readable, '
                'so automatic publication is disabled'
            )

    def _check_verdict(self, record: RightsRecord, reasons: list[str]) -> None:
        if record.verdict is not RightsVerdict.ALLOWED:
            reasons.append(f'Rights verdict is {record.verdict.value}: {record.reason}')

    def _check_identity(self, record: RightsRecord, reasons: list[str]) -> None:
        if record.license_id is None:
            reasons.append('No license identity was resolved')
            return
        if self._matrix.resolve(record.license_id) is None:
            reasons.append(f'Resolved license {record.license_id!r} is not in the policy table')
            return

    def _check_evidence(self, record: RightsRecord, reasons: list[str]) -> None:
        if not self._has_source_evidence(record.evidence):
            reasons.append(
                'Verdict rests only on interpretation: no API field, license file '
                'or human attestation backs it'
            )
        if not self._has_identity_match(record.evidence):
            reasons.append('License identity was never matched against a known license')
        grant = self._matrix.resolve(record.license_id)
        if grant is not None and grant.storefront_listing is StorefrontListing.NOT_LISTED:
            reasons.append(f'{grant.license_id} does not permit listing in a commercial catalog')

    @classmethod
    def _has_source_evidence(cls, evidence: tuple[Evidence, ...]) -> bool:
        return any(item.kind in cls.SOURCE_EVIDENCE_KINDS for item in evidence)

    @staticmethod
    def _has_identity_match(evidence: tuple[Evidence, ...]) -> bool:
        return any(item.kind is EvidenceKind.SPDX_MATCH for item in evidence)
