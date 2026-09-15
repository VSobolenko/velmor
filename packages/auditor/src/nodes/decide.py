from __future__ import annotations

from packages.auditor.src.state import AuditorState
from packages.services.src.clock import Clock
from packages.services.src.domain.rights import RightsAction
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.src.rights.rights_resolver import RightsResolver


class DecideNode:
    """Run the deterministic rights engine and the publication gate.

    Both are pure functions of the accumulated evidence, so this node reaches the
    same verdict when it is re-run from a checkpoint. It makes no model calls and
    holds no policy of its own: the matrix decides what the licence permits and
    the gate decides whether that is enough to publish.
    """

    def __init__(
        self,
        resolver: RightsResolver,
        gate: PublicationGate,
        clock: Clock,
        requested_actions: tuple[RightsAction, ...],
    ) -> None:
        self._resolver = resolver
        self._gate = gate
        self._clock = clock
        self._requested_actions = requested_actions

    async def __call__(self, state: AuditorState) -> dict:
        record = self._resolver.resolve(
            state['candidate'],
            requested_actions=self._requested_actions,
            evidence=tuple(state['evidence']),
            decided_at=self._clock.now(),
        )
        decision = self._gate.decide(state['source'], record)
        return {'record': record, 'decision': decision}
