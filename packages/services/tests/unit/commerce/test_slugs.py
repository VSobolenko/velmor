from __future__ import annotations

from packages.services.src.commerce.slugs import ProductSlug


class TestProductSlug:
    def test_source_qualified_id_is_saleor_safe(self) -> None:
        slug = ProductSlug.for_candidate(
            'openverse:bb619848-465a-4a9d-b061-0580245ddca8'
        )
        assert slug == 'good-openverse-bb619848-465a-4a9d-b061-0580245ddca8'
        assert ':' not in slug

    def test_already_safe_id_is_unchanged_aside_from_prefix(self) -> None:
        assert ProductSlug.for_candidate('item-1') == 'good-item-1'
