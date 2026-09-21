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


class CategorySlug:
    """A category slug, restricted to what a URL segment and Saleor both accept.

    A category slug is proposed by a model and then becomes an identity: it is
    part of the address a buyer opens and part of the key that decides whether a
    category already exists. It is validated rather than rewritten, because a
    silently repaired slug would be a different category from the one that was
    proposed and the second run would propose the original again.
    """

    MAX_CHARS = 64
    _VALID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')

    @classmethod
    def is_valid(cls, slug: str) -> bool:
        return len(slug) <= cls.MAX_CHARS and cls._VALID.fullmatch(slug) is not None
