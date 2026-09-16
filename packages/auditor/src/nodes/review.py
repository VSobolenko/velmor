from __future__ import annotations

from langgraph.types import interrupt

from packages.auditor.src.state import AuditorState
from packages.services.src.clock import Clock
from packages.services.src.domain.review import HumanRuling
from packages.services.src.domain.rights import Evidence, EvidenceKind
from packages.services.src.rights.license_matrix import LicenseMatrix


class ReviewNode:
    """Pause the graph so a person can settle a licence the agent could not.

    This is the graph's only pause point. Everything above ``interrupt`` reads
    state and builds the request payload, so LangGraph restarting this node from
    the top on resume re-derives the same payload rather than repeating a side
    effect. Side effects belong below the interrupt, never above it.

    A person naming a licence resolves an *identity*. It does not widen
    permissions: the matrix still decides what that licence allows, so an
    approval here cannot make a non-commercial licence sellable.
    """

    EXTRACTOR_VERSION = '1.0.0'

    def __init__(self, matrix: LicenseMatrix, clock: Clock) -> None:
        self._matrix = matrix
        self._clock = clock

    async def __call__(self, state: AuditorState) -> dict:
        raw_ruling = interrupt(self._request_for(state))
        ruling = HumanRuling.model_validate(raw_ruling)

        if not ruling.approved or ruling.license_id is None:
            # A person ruled that no licence applies, so nothing is claimed and
            # nothing is resolved: the decision must not fall back to the source's
            # own field after a human has contradicted it.
            return {'human_ruling': ruling, 'license_claim': None, 'resolved_license_id': None}

        attestation = Evidence(
            kind=EvidenceKind.HUMAN_ATTESTATION,
            locator=f'human review item={state["candidate"].id}',
            excerpt=ruling.license_id,
            retrieved_at=self._clock.now(),
            extractor_version=self.EXTRACTOR_VERSION,
        )
        evidence = [*state['evidence'], attestation]

        grant = self._matrix.resolve(ruling.license_id)
        if grant is None:
            # The ruling names a licence the policy table does not know, so the
            # identity does not resolve. It still becomes the claim, so the refusal
            # names what the person ruled instead of reporting no licence at all.
            return {
                'human_ruling': ruling,
                'license_claim': ruling.license_id,
                'evidence': evidence,
            }

        identity_match = Evidence(
            kind=EvidenceKind.SPDX_MATCH,
            locator=f'human review item={state["candidate"].id}',
            excerpt=ruling.license_id,
            retrieved_at=self._clock.now(),
            extractor_version=self.EXTRACTOR_VERSION,
        )
        return {
            'human_ruling': ruling,
            'license_claim': ruling.license_id,
            'resolved_license_id': grant.license_id,
            'evidence': [*evidence, identity_match],
        }

    def _request_for(self, state: AuditorState) -> dict:
        candidate = state['candidate']
        interpretation = state['interpretation']
        return {
            'candidate_id': candidate.id,
            'title': candidate.title,
            'landing_url': candidate.landing_url,
            'declared_license_id': candidate.declared_license_id,
            'interpretation': (interpretation.model_dump() if interpretation is not None else None),
            'investigation_attempts': state['investigation_attempts'],
            'question': 'Which licence applies to this item, if any?',
        }
