from __future__ import annotations

import re


class ProductSlug:
    """Deterministic Saleor product slug derived from a candidate id.

    Shared by the publication bridge and category assignment so a title rename
    cannot orphan the slug, and assign/unassign keep the same identity the
    bridge created. Saleor accepts only Unicode letters, numbers, underscores
    and hyphens in a slug, so characters such as ``:`` in a source-qualified
    candidate id are replaced rather than passed through.
    """

    _UNSAFE = re.compile(r'[^0-9A-Za-z_-]+')

    @classmethod
    def for_candidate(cls, candidate_id: str) -> str:
        safe = cls._UNSAFE.sub('-', candidate_id).strip('-').lower()
        return f'good-{safe}'
