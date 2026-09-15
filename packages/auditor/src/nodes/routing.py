from __future__ import annotations

from packages.auditor.src.node_names import DECIDE, INVESTIGATE, REVIEW
from packages.auditor.src.state import AuditorState


class ResolutionRouter:
    """Choose the next node after a licence resolution attempt.

    This edge is the reason the flow is a graph. How many times to look, when to
    stop looking, and when to hand the question to a person are decisions made
    from accumulated state, not a fixed sequence of calls.

    An identity that resolved from a model reading the page is only as good as
    that reading. When the model is not sure of what it read, the licence still
    resolves but the run does not act on it: it pauses. Otherwise a hesitant
    reading would be laundered into a publication, because a resolved identity is
    an identity match and the page quote is evidence from the page.
    """

    def __init__(self, max_investigation_attempts: int, escalation_confidence: float) -> None:
        self._max_investigation_attempts = max_investigation_attempts
        self._escalation_confidence = escalation_confidence

    def __call__(self, state: AuditorState) -> str:
        if state['resolved_license_id'] is None:
            if state['investigation_attempts'] < self._max_investigation_attempts:
                return INVESTIGATE
            return REVIEW
        if self._is_uncertain(state):
            return REVIEW
        return DECIDE

    def _is_uncertain(self, state: AuditorState) -> bool:
        """Whether the resolved identity rests on a reading the model is unsure of.

        A human ruling settles the identity outright, and a licence the source
        declared itself needs no reading at all, so only an interpretation can be
        uncertain - and only while it is the thing the identity came from.
        """
        if state['human_ruling'] is not None:
            return False
        interpretation = state['interpretation']
        if interpretation is None:
            return False
        return interpretation.confidence < self._escalation_confidence
