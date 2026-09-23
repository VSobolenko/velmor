from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from PIL import Image

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.commerce.errors import (
    PreviewCoverMissingError,
    PreviewDigestMismatchError,
    PreviewNotFoundError,
    PreviewNotRenderableError,
    PreviewOriginUnreachableError,
)
from packages.services.src.commerce.preview import GoodPreview
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.preview import CatalogueCover, CoverSource
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate

ORIGIN_URL = 'https://secret-origin.example/never-leak/high-resolution.png'
CANDIDATE_ID = 'openverse:1'
ATTACHED_AT = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
CACHE_MAX_BYTES = 8_000_000


def build_image(width: int = 2048, height: int = 1024, mode: str = 'RGB') -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), 'red').save(buffer, format='PNG')
    return buffer.getvalue()


def build_entry(
    digest: str,
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
        published_at=ATTACHED_AT,
        content_digest=digest,
        origin_url=ORIGIN_URL,
    )


class Origin:
    """A mock origin that records every request and returns one body."""

    def __init__(self, body: bytes, status: int = 200, fail: bool = False) -> None:
        self._body = body
        self._status = status
        self._fail = fail
        self.requests: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        if self._fail:
            raise httpx.ConnectError('connection refused')
        return httpx.Response(self._status, content=self._body)


def build_preview(
    tmp_path: Path,
    body: bytes,
    status: int = 200,
    fail: bool = False,
) -> tuple[GoodPreview, InMemoryStore, AssetCache, Origin, Candidate]:
    store = InMemoryStore()
    candidate = build_candidate(candidate_id=CANDIDATE_ID)
    cache = AssetCache(root=tmp_path, max_bytes=CACHE_MAX_BYTES)
    origin = Origin(body, status=status, fail=fail)
    http = httpx.AsyncClient(transport=httpx.MockTransport(origin.handler))
    preview = GoodPreview(
        entries=store,
        covers=store,
        cache=cache,
        http=http,
        derivative=PreviewDerivative(cache),
    )
    return preview, store, cache, origin, candidate


@pytest.fixture
def image() -> bytes:
    return build_image()


class TestPreviewOfAGood:
    async def test_a_published_image_is_served_downscaled(
        self, tmp_path: Path, image: bytes
    ) -> None:
        preview, store, _, origin, candidate = build_preview(tmp_path, image)
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry(hashlib.sha256(image).hexdigest()))

        result = await preview.render(CANDIDATE_ID)

        assert result.from_cover is False
        assert result.media_type in ('image/webp', 'image/jpeg')
        assert result.etag == f'"{hashlib.sha256(image).hexdigest()}"'
        with Image.open(io.BytesIO(result.payload)) as rendered:
            assert max(rendered.size) == PreviewDerivative.MAX_EDGE
        assert origin.requests == [ORIGIN_URL]

    async def test_the_derivative_is_cached_so_the_origin_is_read_once(
        self, tmp_path: Path, image: bytes
    ) -> None:
        preview, store, _, origin, candidate = build_preview(tmp_path, image)
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry(hashlib.sha256(image).hexdigest()))

        first = await preview.render(CANDIDATE_ID)
        second = await preview.render(CANDIDATE_ID)

        assert first.payload == second.payload
        assert origin.requests == [ORIGIN_URL]

    async def test_an_original_already_in_the_cache_is_not_fetched(
        self, tmp_path: Path, image: bytes
    ) -> None:
        preview, store, cache, origin, candidate = build_preview(tmp_path, image)
        digest = hashlib.sha256(image).hexdigest()
        cache.put(digest, image)
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry(digest))

        result = await preview.render(CANDIDATE_ID)

        assert result.payload != b''
        assert origin.requests == []

    async def test_a_body_that_is_not_the_cached_original_is_fetched_again(
        self, tmp_path: Path, image: bytes
    ) -> None:
        """A cache file whose name is the digest is re-hashed, not trusted."""
        preview, store, cache, origin, candidate = build_preview(tmp_path, image)
        digest = hashlib.sha256(image).hexdigest()
        cache.put(digest, b'corrupted bytes')
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry(digest))

        await preview.render(CANDIDATE_ID)

        assert origin.requests == [ORIGIN_URL]

    async def test_a_narrow_image_keeps_its_own_shape(
        self, tmp_path: Path
    ) -> None:
        body = build_image(width=400, height=200)
        preview, store, _, _, candidate = build_preview(tmp_path, body)
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry(hashlib.sha256(body).hexdigest()))

        result = await preview.render(CANDIDATE_ID)

        with Image.open(io.BytesIO(result.payload)) as rendered:
            assert rendered.size == (400, 200)


class TestPreviewRefusals:
    async def test_a_withdrawn_good_has_no_preview(self, tmp_path: Path, image: bytes) -> None:
        preview, store, _, origin, candidate = build_preview(tmp_path, image)
        await store.upsert_many((candidate,))
        await store.save_entry(
            build_entry(
                hashlib.sha256(image).hexdigest(), state=CatalogueEntryState.WITHDRAWN
            )
        )

        with pytest.raises(PreviewNotFoundError):
            await preview.render(CANDIDATE_ID)

        assert origin.requests == []

    async def test_a_good_that_is_not_paid_ok_has_no_preview(
        self, tmp_path: Path, image: bytes
    ) -> None:
        preview, store, _, origin, candidate = build_preview(tmp_path, image)
        await store.upsert_many((candidate,))
        await store.save_entry(
            build_entry(
                hashlib.sha256(image).hexdigest(), listing=StorefrontListing.FREE_ONLY
            )
        )

        with pytest.raises(PreviewNotFoundError):
            await preview.render(CANDIDATE_ID)

        assert origin.requests == []

    async def test_an_unknown_good_has_no_preview(self, tmp_path: Path, image: bytes) -> None:
        preview, _, _, origin, _ = build_preview(tmp_path, image)

        with pytest.raises(PreviewNotFoundError):
            await preview.render(CANDIDATE_ID)

        assert origin.requests == []

    async def test_bytes_that_no_longer_match_the_digest_are_refused(
        self, tmp_path: Path, image: bytes
    ) -> None:
        preview, store, cache, _, candidate = build_preview(tmp_path, image)
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry('0' * 64))

        with pytest.raises(PreviewDigestMismatchError):
            await preview.render(CANDIDATE_ID)

        assert cache.scoped(PreviewDerivative.DIRECTORY).has(
            PreviewDerivative.key_for('0' * 64)
        ) is False

    async def test_an_unreachable_origin_is_refused(self, tmp_path: Path) -> None:
        preview, store, _, _, candidate = build_preview(tmp_path, b'', fail=True)
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry('a' * 64))

        with pytest.raises(PreviewOriginUnreachableError):
            await preview.render(CANDIDATE_ID)

    async def test_an_origin_error_is_refused(self, tmp_path: Path) -> None:
        preview, store, _, _, candidate = build_preview(tmp_path, b'', status=503)
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry('a' * 64))

        with pytest.raises(PreviewOriginUnreachableError):
            await preview.render(CANDIDATE_ID)

    async def test_a_payload_that_is_not_an_image_is_refused(self, tmp_path: Path) -> None:
        body = b'this is not an image'
        preview, store, _, _, candidate = build_preview(tmp_path, body)
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry(hashlib.sha256(body).hexdigest()))

        with pytest.raises(PreviewNotRenderableError):
            await preview.render(CANDIDATE_ID)

    @pytest.mark.parametrize(
        'failure',
        [
            PreviewNotFoundError,
            PreviewNotRenderableError,
            PreviewDigestMismatchError,
            PreviewOriginUnreachableError,
        ],
    )
    async def test_no_refusal_message_names_the_origin(
        self, tmp_path: Path, image: bytes, failure: type[Exception]
    ) -> None:
        if failure is PreviewOriginUnreachableError:
            preview, store, _, _, candidate = build_preview(tmp_path, b'', fail=True)
            await store.upsert_many((candidate,))
            await store.save_entry(build_entry('a' * 64))
        elif failure is PreviewDigestMismatchError:
            preview, store, _, _, candidate = build_preview(tmp_path, image)
            await store.upsert_many((candidate,))
            await store.save_entry(build_entry('0' * 64))
        elif failure is PreviewNotRenderableError:
            preview, store, _, _, candidate = build_preview(tmp_path, b'not an image')
            await store.upsert_many((candidate,))
            await store.save_entry(build_entry(hashlib.sha256(b'not an image').hexdigest()))
        else:
            preview, _, _, _, _ = build_preview(tmp_path, image)

        with pytest.raises(failure) as raised:
            await preview.render(CANDIDATE_ID)

        assert ORIGIN_URL not in str(raised.value)


class TestCovers:
    async def test_a_stored_cover_is_preferred_over_the_origin(
        self, tmp_path: Path
    ) -> None:
        cover_body = build_image(width=600, height=600)
        preview, store, cache, origin, candidate = build_preview(tmp_path, b'')
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry('a' * 64))
        derivative = PreviewDerivative(cache)
        derivative.cut('b' * 64, cover_body)
        await store.save_cover(
            CatalogueCover(
                candidate_id=CANDIDATE_ID,
                digest='b' * 64,
                media_type=derivative.media_type,
                source=CoverSource.GENERATED,
                rights_note='generated for this good',
                attached_at=ATTACHED_AT,
            )
        )

        result = await preview.render(CANDIDATE_ID)

        assert result.from_cover is True
        assert result.media_type == derivative.media_type
        assert result.etag == f'"{"b" * 64}"'
        assert origin.requests == []

    async def test_a_cover_whose_bytes_are_gone_is_refused(self, tmp_path: Path) -> None:
        preview, store, _, _, candidate = build_preview(tmp_path, b'')
        await store.upsert_many((candidate,))
        await store.save_entry(build_entry('a' * 64))
        await store.save_cover(
            CatalogueCover(
                candidate_id=CANDIDATE_ID,
                digest='b' * 64,
                media_type='image/webp',
                source=CoverSource.GENERATED,
                rights_note='generated for this good',
                attached_at=ATTACHED_AT,
            )
        )

        with pytest.raises(PreviewCoverMissingError):
            await preview.render(CANDIDATE_ID)
