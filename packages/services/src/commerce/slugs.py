from __future__ import annotations


class ProductSlug:
    """Deterministic Saleor product slug derived from a candidate id.

    Shared by the publication bridge and category assignment so a title rename
    cannot orphan the slug, and assign/unassign keep the same identity the
    bridge created.
    """

    @staticmethod
    def for_candidate(candidate_id: str) -> str:
        return f'good-{candidate_id}'.lower()
