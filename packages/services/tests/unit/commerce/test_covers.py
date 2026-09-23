from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.covers import CoverAttacher
from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.commerce.errors import (
    CatalogueEntryNotFoundError,
    CoverRefusedError,
    PreviewNotRenderableError,
)
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.preview import CoverSource
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
CANDIDATE_ID = 'openverse:1'
RIGHTS_NOTE = 'generated for this good by the operator; depicts no third-party work'


def build_image(width: int = 2400, height: int = 1200) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), 'blue').save(buffer, format='PNG')
    return buffer.getvalue()


def build_entry(
    state: CatalogueEntryState = CatalogueEntryState.PUBLISHED,
    listing: StorefrontListing = StorefrontListing.PAID_OK,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=CANDIDATE_ID,
        source_id='openverse',
        saleor_product_id='product-1',
        saleor_variant_id='variant-1',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=(),
        listing=listing,
        state=state,
        withdrawal_reason='withdrawn for test' if state is CatalogueEntryState.WITHDRAWN else None,
        published_at=NOW,
        content_digest='a' * 64,
        origin_url='https://secret-origin.example/never-leak/asset.bin',
    )


def build_attacher(tmp_path: Path) -> tuple[CoverAttacher, InMemoryStore, AssetCache]:
    store = InMemoryStore()
    cache = AssetCache(root=tmp_path, max_bytes=8_000_000)
    attacher = CoverAttacher(
        entries=store,
        covers=store,
        derivative=PreviewDerivative(cache),
        clock=lambda: NOW,
    )
    return attacher, store, cache


def write_image(tmp_path: Path, body: bytes) -> Path:
    path = tmp_path / 'cover.png'
    path.write_bytes(body)
    return path


class TestAttachingACover:
    async def test_a_cover_is_stored_against_its_good(self, tmp_path: Path) -> None:
        attacher, store, _ = build_attacher(tmp_path)
        await store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await store.save_entry(build_entry())
        body = build_image()

        cover = await attacher.attach(
            CANDIDATE_ID, write_image(tmp_path, body), CoverSource.GENERATED, RIGHTS_NOTE
        )

        assert cover.candidate_id == CANDIDATE_ID
        assert cover.digest == hashlib.sha256(body).hexdigest()
        assert cover.source is CoverSource.GENERATED
        assert cover.rights_note == RIGHTS_NOTE
        assert cover.attached_at == NOW
        assert await store.cover_for(CANDIDATE_ID) == cover

    async def test_the_cover_is_kept_as_a_bounded_derivative(self, tmp_path: Path) -> None:
        attacher, store, cache = build_attacher(tmp_path)
        await store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await store.save_entry(build_entry())
        body = build_image(width=2400, height=1200)

        cover = await attacher.attach(
            CANDIDATE_ID, write_image(tmp_path, body), CoverSource.GENERATED, RIGHTS_NOTE
        )

        stored = PreviewDerivative(cache).cached(cover.digest)
        assert stored is not None
        with Image.open(io.BytesIO(stored)) as rendered:
            assert max(rendered.size) == PreviewDerivative.MAX_EDGE
        assert cover.media_type == PreviewDerivative(cache).media_type

    async def test_the_original_file_is_not_stored_as_the_cover(self, tmp_path: Path) -> None:
        """A cover is reached by digest through the derivative, never as an original."""
        attacher, store, cache = build_attacher(tmp_path)
        await store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await store.save_entry(build_entry())
        body = build_image()

        cover = await attacher.attach(
            CANDIDATE_ID, write_image(tmp_path, body), CoverSource.DOWNLOADED, RIGHTS_NOTE
        )

        assert cache.get(cover.digest) is None

    async def test_attaching_again_replaces_the_cover(self, tmp_path: Path) -> None:
        attacher, store, _ = build_attacher(tmp_path)
        await store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await store.save_entry(build_entry())
        first = build_image(width=800, height=600)
        second = build_image(width=600, height=400)

        await attacher.attach(
            CANDIDATE_ID, write_image(tmp_path, first), CoverSource.GENERATED, RIGHTS_NOTE
        )
        replaced = await attacher.attach(
            CANDIDATE_ID, write_image(tmp_path, second), CoverSource.GENERATED, RIGHTS_NOTE
        )

        assert await store.cover_for(CANDIDATE_ID) == replaced
        assert replaced.digest == hashlib.sha256(second).hexdigest()

    async def test_the_attached_covers_are_listed(self, tmp_path: Path) -> None:
        attacher, store, _ = build_attacher(tmp_path)
        for candidate_id in (CANDIDATE_ID, 'openverse:2'):
            await store.upsert_many((build_candidate(candidate_id=candidate_id),))
            await store.save_entry(
                build_entry().model_copy(update={'candidate_id': candidate_id})
            )
            await attacher.attach(
                candidate_id,
                write_image(tmp_path, build_image()),
                CoverSource.GENERATED,
                RIGHTS_NOTE,
            )

        listed = await attacher.attached()

        assert tuple(cover.candidate_id for cover in listed) == (
            'openverse:1',
            'openverse:2',
        )


class TestCoverRefusals:
    async def test_a_cover_for_an_unknown_good_is_refused(self, tmp_path: Path) -> None:
        attacher, _, _ = build_attacher(tmp_path)

        with pytest.raises(CatalogueEntryNotFoundError):
            await attacher.attach(
                CANDIDATE_ID,
                write_image(tmp_path, build_image()),
                CoverSource.GENERATED,
                RIGHTS_NOTE,
            )

    async def test_a_cover_for_a_withdrawn_good_is_refused(self, tmp_path: Path) -> None:
        attacher, store, _ = build_attacher(tmp_path)
        await store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await store.save_entry(build_entry(state=CatalogueEntryState.WITHDRAWN))

        with pytest.raises(CatalogueEntryNotFoundError):
            await attacher.attach(
                CANDIDATE_ID,
                write_image(tmp_path, build_image()),
                CoverSource.GENERATED,
                RIGHTS_NOTE,
            )

    async def test_a_cover_for_a_free_only_good_is_refused(self, tmp_path: Path) -> None:
        attacher, store, _ = build_attacher(tmp_path)
        await store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await store.save_entry(build_entry(listing=StorefrontListing.FREE_ONLY))

        with pytest.raises(CatalogueEntryNotFoundError):
            await attacher.attach(
                CANDIDATE_ID,
                write_image(tmp_path, build_image()),
                CoverSource.GENERATED,
                RIGHTS_NOTE,
            )

    async def test_a_cover_with_no_recorded_permission_is_refused(self, tmp_path: Path) -> None:
        attacher, store, _ = build_attacher(tmp_path)
        await store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await store.save_entry(build_entry())

        with pytest.raises(CoverRefusedError):
            await attacher.attach(
                CANDIDATE_ID,
                write_image(tmp_path, build_image()),
                CoverSource.DOWNLOADED,
                '   ',
            )

        assert await store.cover_for(CANDIDATE_ID) is None

    async def test_a_file_that_is_not_an_image_is_refused(self, tmp_path: Path) -> None:
        attacher, store, _ = build_attacher(tmp_path)
        await store.upsert_many((build_candidate(candidate_id=CANDIDATE_ID),))
        await store.save_entry(build_entry())

        with pytest.raises(PreviewNotRenderableError):
            await attacher.attach(
                CANDIDATE_ID,
                write_image(tmp_path, b'this is not an image'),
                CoverSource.DOWNLOADED,
                RIGHTS_NOTE,
            )

        assert await store.cover_for(CANDIDATE_ID) is None
