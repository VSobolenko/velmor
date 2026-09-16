from __future__ import annotations

from packages.auditor.src.nodes.decide import DecideNode
from packages.auditor.tests.conftest import FixedClock, build_state
from packages.services.src.domain.rights import EvidenceKind
from packages.services.src.rights.engine import RightsEngine
from packages.services.tests.conftest import build_candidate, build_evidence, build_spec


class TestDecideNode:
    async def test_a_supported_licence_is_publishable(
        self, clock: FixedClock, engine: RightsEngine
    ) -> None:
        node = DecideNode(engine.resolver, engine.gate, clock, RightsEngine.STOREFRONT_ACTIONS)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            license_claim='CC0-1.0',
            evidence=build_evidence((EvidenceKind.SOURCE_API_FIELD, EvidenceKind.SPDX_MATCH)),
        )

        result = await node(state)

        assert result['decision'].publishable is True
        assert result['decision'].reasons == ()
        assert result['record'].license_id == 'CC0-1.0'

    async def test_a_non_commercial_licence_is_refused_with_a_reason(
        self, clock: FixedClock, engine: RightsEngine
    ) -> None:
        node = DecideNode(engine.resolver, engine.gate, clock, RightsEngine.STOREFRONT_ACTIONS)
        state = build_state(
            build_candidate(license_id='CC-BY-NC-4.0'),
            build_spec(),
            license_claim='CC-BY-NC-4.0',
            evidence=build_evidence((EvidenceKind.SOURCE_API_FIELD, EvidenceKind.SPDX_MATCH)),
        )

        result = await node(state)

        assert result['decision'].publishable is False
        assert result['decision'].reasons

    async def test_an_interpreted_identity_is_refused(
        self, clock: FixedClock, engine: RightsEngine
    ) -> None:
        node = DecideNode(engine.resolver, engine.gate, clock, RightsEngine.STOREFRONT_ACTIONS)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            license_claim='CC0-1.0',
            evidence=build_evidence((EvidenceKind.LLM_EXTRACTION, EvidenceKind.SPDX_MATCH)),
        )

        result = await node(state)

        assert result['decision'].publishable is False
        assert any('interpretation' in reason for reason in result['decision'].reasons)

    async def test_rerunning_the_node_reaches_the_same_verdict(
        self, clock: FixedClock, engine: RightsEngine
    ) -> None:
        node = DecideNode(engine.resolver, engine.gate, clock, RightsEngine.STOREFRONT_ACTIONS)
        state = build_state(
            build_candidate(license_id='CC-BY-NC-4.0'),
            build_spec(),
            license_claim='CC-BY-NC-4.0',
            evidence=build_evidence((EvidenceKind.SOURCE_API_FIELD, EvidenceKind.SPDX_MATCH)),
        )

        first = await node(state)
        second = await node(state)

        assert first['decision'] == second['decision']
        assert first['record'] == second['record']


class TestDecideNodeJudgesTheEstablishedClaim:
    """The node rules on the claim the run settled on, not on the source's field.

    When it read the field instead, an identity a person or a page had already
    established never reached the verdict: the record was refused for whatever the
    source happened to declare, while its own evidence attested another licence.
    """

    async def test_the_established_claim_outranks_the_source_field(
        self, clock: FixedClock, engine: RightsEngine
    ) -> None:
        node = DecideNode(engine.resolver, engine.gate, clock, RightsEngine.STOREFRONT_ACTIONS)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            license_claim='CC-BY-NC-4.0',
            evidence=build_evidence(
                (EvidenceKind.SOURCE_API_FIELD, EvidenceKind.SPDX_MATCH), excerpt='CC-BY-NC-4.0'
            ),
        )

        result = await node(state)

        assert result['record'].license_id == 'CC-BY-NC-4.0'
        assert result['decision'].publishable is False

    async def test_a_claim_the_source_never_declared_can_be_published(
        self, clock: FixedClock, engine: RightsEngine
    ) -> None:
        node = DecideNode(engine.resolver, engine.gate, clock, RightsEngine.STOREFRONT_ACTIONS)
        state = build_state(
            build_candidate(license_id=None),
            build_spec(),
            license_claim='CC0-1.0',
            evidence=build_evidence(
                (EvidenceKind.HUMAN_ATTESTATION, EvidenceKind.SPDX_MATCH), excerpt='CC0-1.0'
            ),
        )

        result = await node(state)

        assert result['decision'].publishable is True
        assert result['record'].license_id == 'CC0-1.0'

    async def test_an_unresolvable_claim_is_refused_under_its_own_name(
        self, clock: FixedClock, engine: RightsEngine
    ) -> None:
        node = DecideNode(engine.resolver, engine.gate, clock, RightsEngine.STOREFRONT_ACTIONS)
        state = build_state(
            build_candidate(license_id='CC0-1.0'),
            build_spec(),
            license_claim='Velmor-Internal-Ware',
            evidence=build_evidence(
                (EvidenceKind.HUMAN_ATTESTATION, EvidenceKind.SPDX_MATCH),
                excerpt='Velmor-Internal-Ware',
            ),
        )

        result = await node(state)

        assert result['decision'].publishable is False
        assert 'Velmor-Internal-Ware' in ' '.join(result['decision'].reasons)
