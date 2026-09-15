from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class SourceTier(StrEnum):
    """How much Velmor trusts a source's machine-readable rights metadata.

    The tier caps what the publication gate will ever allow, independently of
    what the rights engine concludes about an individual item.

    * ``A`` - the platform exposes a per-item rights identifier that maps to a
      known license. Machine-decidable.
    * ``B`` - the platform exposes rights prose or a coarse license field. An
      agent must interpret it, and the interpretation must resolve to a known
      license before the item can be published.
    * ``C`` - no machine-readable rights at all. Never auto-published; kept only
      so a human can inspect the funnel.
    """

    A = 'a'
    B = 'b'
    C = 'c'


class SourceKind(StrEnum):
    """Transport a connector uses to talk to the source."""

    REST_API = 'rest_api'
    GRAPHQL_API = 'graphql_api'
    OAI_PMH = 'oai_pmh'
    SITEMAP = 'sitemap'


class SourceSpec(BaseModel):
    """Declared contract of one upstream source.

    ``required_env`` is the credential contract: the source registry refuses to
    start when an enabled source is missing any of these keys, so a half
    configured source fails loudly instead of returning empty pages.
    """

    model_config = {'frozen': True}

    id: str
    name: str
    kind: SourceKind
    tier: SourceTier
    base_url: str
    required_env: tuple[str, ...]
    enabled: bool
