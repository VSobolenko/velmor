from __future__ import annotations

from packages.services.src.domain.rights import RightsAction, RightsVerdict
from packages.services.src.rights.rights_resolver import RightsResolver
from packages.services.tests.conftest import (
    ALL_ACTIONS,
    DECIDED_AT,
    build_candidate,
    build_evidence,
)


class TestRightsResolverAllowed:
    def test_permissive_license_grants_every_requested_action(
        self, resolver: RightsResolver
    ) -> None:
        record = resolver.resolve(
            build_candidate('MIT'),
            requested_actions=ALL_ACTIONS,
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.ALLOWED
        assert record.license_id == 'MIT'
        assert set(record.requested_actions) <= set(record.granted_actions)

    def test_granted_actions_and_obligations_come_from_the_policy_table(
        self, resolver: RightsResolver
    ) -> None:
        record = resolver.resolve(
            build_candidate('Apache-2.0'),
            requested_actions=ALL_ACTIONS,
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.ALLOWED
        assert any('NOTICE' in obligation for obligation in record.obligations)

    def test_resolves_a_human_alias_before_deciding(self, resolver: RightsResolver) -> None:
        record = resolver.resolve(
            build_candidate('apache 2.0'),
            requested_actions=ALL_ACTIONS,
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.ALLOWED
        assert record.license_id == 'Apache-2.0'


class TestRightsResolverDenied:
    def test_denies_modification_under_no_derivatives(self, resolver: RightsResolver) -> None:
        record = resolver.resolve(
            build_candidate('CC-BY-ND-4.0'),
            requested_actions=(RightsAction.RESELL, RightsAction.MODIFY),
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.DENIED
        assert 'modify' in record.reason
        assert RightsAction.MODIFY not in record.granted_actions

    def test_denies_resale_under_non_commercial_license(self, resolver: RightsResolver) -> None:
        record = resolver.resolve(
            build_candidate('CC-BY-NC-4.0'),
            requested_actions=(RightsAction.RESELL,),
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.DENIED
        assert 'resell' in record.reason

    def test_denies_sublicensing_under_copyleft(self, resolver: RightsResolver) -> None:
        record = resolver.resolve(
            build_candidate('GPL-3.0-only'),
            requested_actions=(RightsAction.SUBLICENSE,),
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.DENIED

    def test_a_denial_keeps_the_license_identity_for_the_audit_trail(
        self, resolver: RightsResolver
    ) -> None:
        record = resolver.resolve(
            build_candidate('CC-BY-NC-4.0'),
            requested_actions=(RightsAction.RESELL,),
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.license_id == 'CC-BY-NC-4.0'
        assert record.engine_version


class TestRightsResolverUnknown:
    def test_missing_license_is_unknown_never_allowed(self, resolver: RightsResolver) -> None:
        record = resolver.resolve(
            build_candidate(None),
            requested_actions=ALL_ACTIONS,
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.UNKNOWN
        assert record.license_id is None
        assert record.granted_actions == ()

    def test_unrecognised_license_is_unknown_never_permissive(
        self, resolver: RightsResolver
    ) -> None:
        record = resolver.resolve(
            build_candidate('proprietary-eula-v3'),
            requested_actions=ALL_ACTIONS,
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.UNKNOWN
        assert 'proprietary-eula-v3' in record.reason

    def test_unknown_outcome_is_not_silently_upgraded(self, resolver: RightsResolver) -> None:
        record = resolver.resolve(
            build_candidate(None),
            requested_actions=(),
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.verdict is RightsVerdict.UNKNOWN

    def test_verdict_is_stamped_with_engine_version_and_time(
        self, resolver: RightsResolver
    ) -> None:
        record = resolver.resolve(
            build_candidate('MIT'),
            requested_actions=ALL_ACTIONS,
            evidence=build_evidence(()),
            decided_at=DECIDED_AT,
        )

        assert record.decided_at == DECIDED_AT
        assert record.engine_version == RightsResolver.ENGINE_VERSION
