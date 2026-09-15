from __future__ import annotations

from collections.abc import Sequence

from packages.core.src.errors import SourceNotConfiguredError, UnknownSourceError
from packages.services.src.domain.source import SourceKind, SourceSpec, SourceTier
from packages.services.src.sources.credentials import CredentialSource


class DefaultSources:
    """The sources Velmor is willing to crawl.

    This is an allowlist, not a starting point. Adding a source is a reviewed
    change because it widens what the platform may publish. Tier A means the
    platform reports a per-item license that maps to SPDX; nothing here is tier C
    on purpose, since tier C can never be auto-published.

    ``enabled`` also gates on the connector existing. A source whose connector has
    not been written yet stays disabled, so an enabled source always means
    "crawlable", never "declared but unimplemented".
    """

    TABLE: tuple[SourceSpec, ...] = (
        SourceSpec(
            id='openverse',
            name='Openverse',
            kind=SourceKind.REST_API,
            tier=SourceTier.A,
            base_url='https://api.openverse.org/v1',
            required_env=(),
            enabled=True,
        ),
        SourceSpec(
            id='wikimedia-commons',
            name='Wikimedia Commons',
            kind=SourceKind.REST_API,
            tier=SourceTier.A,
            base_url='https://commons.wikimedia.org/w/api.php',
            required_env=(),
            enabled=False,
        ),
        SourceSpec(
            id='github',
            name='GitHub',
            kind=SourceKind.REST_API,
            tier=SourceTier.A,
            base_url='https://api.github.com',
            required_env=('GITHUB_TOKEN',),
            enabled=False,
        ),
        SourceSpec(
            id='huggingface',
            name='Hugging Face Hub',
            kind=SourceKind.REST_API,
            tier=SourceTier.A,
            base_url='https://huggingface.co/api',
            required_env=('HUGGINGFACE_TOKEN',),
            enabled=False,
        ),
    )


class SourceRegistry:
    """Resolve and validate the sources a run may touch.

    Credentials are declared per source rather than required globally, so
    enabling a source without its secrets fails at startup with a message naming
    the missing keys, instead of silently returning empty pages at crawl time.
    """

    def __init__(self, specs: Sequence[SourceSpec], loader: CredentialSource) -> None:
        self._by_id: dict[str, SourceSpec] = {spec.id: spec for spec in specs}
        self._specs: tuple[SourceSpec, ...] = tuple(specs)
        self._loader = loader

    def all_specs(self) -> tuple[SourceSpec, ...]:
        return self._specs

    def enabled(self) -> tuple[SourceSpec, ...]:
        return tuple(spec for spec in self._specs if spec.enabled)

    def by_id(self, source_id: str) -> SourceSpec:
        spec = self._by_id.get(source_id)
        if spec is None:
            raise UnknownSourceError(
                f'Source {source_id!r} is not registered. '
                f'Known ids: {", ".join(sorted(self._by_id))}'
            )
        return spec

    def validate_credentials(self) -> None:
        missing_by_source = {
            spec.id: tuple(key for key in spec.required_env if not self._loader.has(key))
            for spec in self.enabled()
        }
        incomplete = {sid: keys for sid, keys in missing_by_source.items() if keys}
        if not incomplete:
            return
        details = '; '.join(
            f'{sid} needs {", ".join(keys)}' for sid, keys in sorted(incomplete.items())
        )
        raise SourceNotConfiguredError(
            f'Enabled sources are missing credentials: {details}. '
            f'Add them to {self._loader.env_file} or disable the source.'
        )
