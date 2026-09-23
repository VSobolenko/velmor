from __future__ import annotations

import io

import pytest
from PIL import Image

from packages.services.src.commerce.errors import PreviewNotRenderableError
from packages.services.src.commerce.image_payload import ImagePayload

PNG_SIZE = (64, 48)
SVG_BODY = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
OVER_BOUND_SIZE = (8000, 9000)


def build_png(width: int = PNG_SIZE[0], height: int = PNG_SIZE[1]) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), 'red').save(buffer, format='PNG')
    return buffer.getvalue()


def declare_pixels(body: bytes, width: int, height: int) -> bytes:
    """Rewrite a PNG's IHDR dimensions so the header declares more pixels.

    The bytes stay a valid PNG header, so the payload decodes only if the caller
    ignores the declaration; that is exactly what the bound exists to prevent.
    """
    return body[:16] + width.to_bytes(4, 'big') + height.to_bytes(4, 'big') + body[24:]


def truncate(body: bytes) -> bytes:
    return body[: len(body) // 2]


class TestImagePayload:
    def test_a_png_payload_is_renderable_and_decodes_to_its_dimensions(self) -> None:
        body = build_png()

        frame = ImagePayload.frame(body)

        assert ImagePayload.can_render(body) is True
        assert frame.size == PNG_SIZE

    def test_an_svg_payload_is_not_renderable(self) -> None:
        with pytest.raises(PreviewNotRenderableError) as raised:
            ImagePayload.frame(SVG_BODY)

        assert ImagePayload.can_render(SVG_BODY) is False
        assert str(raised.value) == ImagePayload.NOT_RENDERABLE_REASON

    def test_a_payload_over_the_pixel_bound_is_refused_by_both_methods(self) -> None:
        body = declare_pixels(build_png(), *OVER_BOUND_SIZE)
        assert OVER_BOUND_SIZE[0] * OVER_BOUND_SIZE[1] > ImagePayload.MAX_DECODE_PIXELS

        with pytest.raises(PreviewNotRenderableError):
            ImagePayload.frame(body)

        assert ImagePayload.can_render(body) is False

    def test_a_truncated_png_is_refused_by_both_methods(self) -> None:
        body = truncate(build_png())

        with pytest.raises(PreviewNotRenderableError):
            ImagePayload.frame(body)

        assert ImagePayload.can_render(body) is False
