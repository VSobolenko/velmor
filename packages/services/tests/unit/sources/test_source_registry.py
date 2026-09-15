from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.src.errors import SourceNotConfiguredError, UnknownSourceError
from packages.services.src.domain.source import SourceKind, SourceSpec, SourceTier
from packages.services.src.sources.source_registry import SourceRegistry


class StubCredentials:
    """Credential presence backed by a plain set, so no ``.env`` file is needed."""

    def __init__(self, present: set[str]) -> None:
        self._present = present
        self.env_file = Path('stub/.env.test')

    def has(self, key: str) -> bool:
        return key in self._present


def build_spec(
    source_id: str,
    *,
    enabled: bool,
    required_env: tuple[str, ...] = (),
    tier: SourceTier = SourceTier.A,
) -> SourceSpec:
    return SourceSpec(
        id=source_id,
        name=source_id.title(),
        kind=SourceKind.REST_API,
        tier=tier,
        base_url='https://example.test',
        required_env=required_env,
        enabled=enabled,
    )


class TestSourceRegistrySelection:
    def test_returns_only_enabled_sources(self) -> None:
        registry = SourceRegistry(
            [
                build_spec('open', enabled=True),
                build_spec('closed', enabled=False),
            ],
            StubCredentials(set()),
        )

        assert [spec.id for spec in registry.enabled()] == ['open']

    def test_looks_up_a_spec_by_id(self) -> None:
        registry = SourceRegistry([build_spec('open', enabled=True)], StubCredentials(set()))

        assert registry.by_id('open').id == 'open'

    def test_unknown_id_names_the_known_ones(self) -> None:
        registry = SourceRegistry(
            [build_spec('open', enabled=True), build_spec('other', enabled=False)],
            StubCredentials(set()),
        )

        with pytest.raises(UnknownSourceError) as error:
            registry.by_id('missing')

        assert 'open' in str(error.value)
        assert 'other' in str(error.value)


class TestSourceRegistryCredentials:
    def test_disabled_source_never_needs_credentials(self) -> None:
        registry = SourceRegistry(
            [build_spec('needs-key', enabled=False, required_env=('TOKEN',))],
            StubCredentials(set()),
        )

        registry.validate_credentials()

    def test_enabled_source_without_declared_keys_passes(self) -> None:
        registry = SourceRegistry(
            [build_spec('open', enabled=True)],
            StubCredentials(set()),
        )

        registry.validate_credentials()

    def test_satisfied_enabled_source_passes(self) -> None:
        registry = SourceRegistry(
            [build_spec('keyed', enabled=True, required_env=('TOKEN',))],
            StubCredentials({'TOKEN'}),
        )

        registry.validate_credentials()

    def test_missing_key_raises_and_names_the_source_and_key(self) -> None:
        registry = SourceRegistry(
            [build_spec('keyed', enabled=True, required_env=('TOKEN', 'SECRET'))],
            StubCredentials({'TOKEN'}),
        )

        with pytest.raises(SourceNotConfiguredError) as error:
            registry.validate_credentials()

        message = str(error.value)
        assert 'keyed' in message
        assert 'SECRET' in message
        assert 'TOKEN' not in message.replace('SECRET', '')

    def test_reports_every_incomplete_source_at_once(self) -> None:
        registry = SourceRegistry(
            [
                build_spec('first', enabled=True, required_env=('FIRST_KEY',)),
                build_spec('second', enabled=True, required_env=('SECOND_KEY',)),
            ],
            StubCredentials(set()),
        )

        with pytest.raises(SourceNotConfiguredError) as error:
            registry.validate_credentials()

        assert 'first' in str(error.value)
        assert 'second' in str(error.value)
