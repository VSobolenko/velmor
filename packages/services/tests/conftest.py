from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from packages.services.src.connectors.contract import SourceConnector
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.query import SearchQuery
from packages.services.src.domain.rights import (
    Evidence,
    EvidenceKind,
    RightsAction,
    RightsRecord,
    RightsVerdict,
)
from packages.services.src.domain.source import SourceKind, SourceSpec, SourceTier
from packages.services.src.rights.license_grants import DefaultLicenseGrants
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.src.rights.rights_resolver import RightsResolver

DECIDED_AT = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

ALL_ACTIONS: tuple[RightsAction, ...] = (
    RightsAction.RESELL,
    RightsAction.REDISTRIBUTE,
    RightsAction.MODIFY,
    RightsAction.SUBLICENSE,
)


@pytest.fixture
def matrix() -> LicenseMatrix:
    return LicenseMatrix(DefaultLicenseGrants.TABLE)


@pytest.fixture
def resolver(matrix: LicenseMatrix) -> RightsResolver:
    return RightsResolver(matrix)


@pytest.fixture
def gate(matrix: LicenseMatrix) -> PublicationGate:
    return PublicationGate(matrix)


@pytest.fixture
def tier_a_spec() -> SourceSpec:
    return SourceSpec(
        id='openverse',
        name='Openverse',
        kind=SourceKind.REST_API,
        tier=SourceTier.A,
        base_url='https://api.openverse.org/v1',
        required_env=(),
        enabled=True,
    )


def build_spec(
    source_id: str = 'openverse',
    tier: SourceTier = SourceTier.A,
    enabled: bool = True,
) -> SourceSpec:
    return SourceSpec(
        id=source_id,
        name=source_id.title(),
        kind=SourceKind.REST_API,
        tier=tier,
        base_url=f'https://{source_id}.test/api',
        required_env=(),
        enabled=enabled,
    )


def build_candidate(
    license_id: str | None = 'CC0-1.0',
    candidate_id: str = 'openverse:1',
    title: str = 'Sample good',
    source_id: str = 'openverse',
    content_type: str = 'image',
) -> Candidate:
    return Candidate(
        id=candidate_id,
        source_id=source_id,
        title=title,
        landing_url=f'https://{source_id}.test/items/{candidate_id}',
        creator='Example Author',
        content_type=content_type,
        declared_license_id=license_id,
        declared_license_text=license_id,
        download_url=f'https://{source_id}.test/items/{candidate_id}.bin',
        size_bytes=1024,
    )


def build_evidence(
    kinds: tuple[EvidenceKind, ...],
    excerpt: str = 'CC-BY-4.0',
) -> tuple[Evidence, ...]:
    return tuple(
        Evidence(
            kind=kind,
            locator=f'https://example.test/evidence/{kind.value}',
            excerpt=excerpt,
            retrieved_at=DECIDED_AT,
            extractor_version='1.0.0',
        )
        for kind in kinds
    )


def build_record(
    license_id: str | None = 'CC-BY-4.0',
    verdict: str = 'allowed',
    evidence_kinds: tuple[EvidenceKind, ...] = (
        EvidenceKind.SOURCE_API_FIELD,
        EvidenceKind.SPDX_MATCH,
    ),
) -> RightsRecord:
    return RightsRecord(
        candidate_id='openverse:1',
        source_id='openverse',
        license_id=license_id,
        requested_actions=ALL_ACTIONS,
        verdict=RightsVerdict(verdict),
        granted_actions=ALL_ACTIONS,
        obligations=(),
        evidence=build_evidence(evidence_kinds),
        reason='built for test',
        engine_version=RightsResolver.ENGINE_VERSION,
        decided_at=DECIDED_AT,
    )


class FakeCredentials:
    """A credential store holding a fixed set of keys."""

    def __init__(self, present: tuple[str, ...] = ()) -> None:
        self._present = present

    @property
    def env_file(self) -> Path:
        return Path('fake.env')

    def has(self, key: str) -> bool:
        return key in self._present


class FakeConnector(SourceConnector):
    """Returns a fixed candidate list and records every query it received."""

    def __init__(self, spec: SourceSpec, candidates: tuple[Candidate, ...]) -> None:
        super().__init__(spec)
        self._candidates = candidates
        self.queries: list[SearchQuery] = []

    async def discover(self, query: SearchQuery) -> tuple[Candidate, ...]:
        self.queries.append(query)
        return self._candidates


class FailingConnector(SourceConnector):
    """A source that is unreachable, as a run must survive it."""

    def __init__(self, spec: SourceSpec, reason: str) -> None:
        super().__init__(spec)
        self._reason = reason

    async def discover(self, query: SearchQuery) -> tuple[Candidate, ...]:
        raise ConnectionError(self._reason)


class FakeConnectorFactory:
    """Hands out prepared connectors by source id, recording which were asked for."""

    def __init__(self, connectors: dict[str, SourceConnector]) -> None:
        self._connectors = connectors
        self.created: list[str] = []

    def create(self, spec: SourceSpec) -> SourceConnector:
        self.created.append(spec.id)
        return self._connectors[spec.id]
