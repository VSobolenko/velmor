from __future__ import annotations

import io

from PIL import Image, features

from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.errors import PreviewNotFoundError


class PreviewDerivative:
    """The bounded, web-sized version of an image we show before purchase.

    One class rather than two, because the preview of a good and an attached
    cover are the same operation over different bytes: both are shown to a buyer
    before payment, both must be bounded so a catalogue page does not ship
    multi-megabyte files, and both are keyed by the digest of the bytes they came
    from so identical bytes share one file. They live under
    ``<delivery cache>/previews``, a subdirectory of the cache the download path
    already uses, so there is one delivery cache on the host and not two.

    ``MAX_EDGE`` is 1024: a product card is at most a few hundred CSS pixels
    wide, and a card image drawn at twice that on a dense display still fits
    inside 1024 without being downscaled again by the browser.
    """

    MAX_EDGE = 1024
    MAX_DECODE_PIXELS = 64_000_000
    QUALITY = 82
    DIRECTORY = 'previews'
    WEBP_MEDIA_TYPE = 'image/webp'
    JPEG_MEDIA_TYPE = 'image/jpeg'
    WEBP_FORMAT = 'WEBP'
    JPEG_FORMAT = 'JPEG'

    def __init__(self, cache: AssetCache) -> None:
        self._cache = cache.scoped(self.DIRECTORY)

    @property
    def max_bytes(self) -> int:
        """The budget of the cache the derivative must fit in to be kept."""
        return self._cache.max_bytes

    @property
    def media_type(self) -> str:
        """What ``cut`` produces, probed rather than guessed.

        WebP is the format a browser is entitled to receive here and Pillow
        either has the encoder compiled in or it does not; probing the feature is
        how the answer is known without attempting a save and catching the
        failure.
        """
        if features.check('webp'):
            return self.WEBP_MEDIA_TYPE
        return self.JPEG_MEDIA_TYPE

    def cached(self, digest: str) -> bytes | None:
        """The derivative already cut from these bytes, if one was kept."""
        return self._cache.get(self.key_for(digest))

    def cut(self, digest: str, body: bytes) -> bytes:
        """Downscale ``body``, encode it, and keep it when it fits the budget.

        A derivative larger than the cache budget is still returned and still
        served; it is simply not written, so a single oversized image cannot
        evict the cache or fail the request. That is the design's stated
        behaviour and it is why ``put`` is not called unconditionally.
        """
        encoded = self.encode(body)
        if len(encoded) <= self.max_bytes:
            self._cache.put(self.key_for(digest), encoded)
        return encoded

    def encode(self, body: bytes) -> bytes:
        """The downscaled, encoded bytes for a decodable image.

        Pillow documents that ``Image.open`` raises ``UnidentifiedImageError``, an
        ``OSError`` subclass, when "the image cannot be opened and identified"
        (Pillow reference, Image module), and raises ``OSError`` for a payload
        truncated while decoding. It also raises ``DecompressionBombError``, a
        plain ``Exception``, when an image declares more than twice
        ``Image.MAX_IMAGE_PIXELS``; that class is named separately because it is
        not an ``OSError``. The contract makes every one of them a refusal - a
        preview request falls back to the storefront's own placeholder - so
        translating them is the logic here rather than a catch that hides a
        failure. No predicate answers "is this a decodable image" without
        attempting the decode, and sniffing magic bytes by hand would refuse
        formats Pillow handles.
        """
        try:
            with Image.open(io.BytesIO(body)) as opened:
                if opened.width * opened.height > self.MAX_DECODE_PIXELS:
                    raise PreviewNotFoundError('the payload is not a decodable image')
                prepared = self._prepared(opened)
        except Image.DecompressionBombError as error:
            raise PreviewNotFoundError('the payload is not a decodable image') from error
        except OSError as error:
            raise PreviewNotFoundError('the payload is not a decodable image') from error
        prepared.thumbnail((self.MAX_EDGE, self.MAX_EDGE), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        prepared.save(buffer, format=self._format(), quality=self.QUALITY)
        return buffer.getvalue()

    @classmethod
    def key_for(cls, digest: str) -> str:
        """The cache key for the derivative of these bytes.

        The edge is part of the key so a second derivative size cannot overwrite
        this one; the key stays digest-derived so two goods with the same bytes
        share a derivative.
        """
        return f'{digest}-{cls.MAX_EDGE}'

    def _prepared(self, opened: Image.Image) -> Image.Image:
        """The frame to encode, with the alpha WebP can carry and JPEG cannot.

        A transparent PNG flattened straight to RGB comes out black where it was
        transparent, which on a catalogue card reads as a broken image.
        """
        transparent = 'A' in opened.getbands() or (
            opened.mode == 'P' and 'transparency' in opened.info
        )
        if transparent and self.media_type == self.WEBP_MEDIA_TYPE:
            return opened.convert('RGBA')
        return opened.convert('RGB')

    def _format(self) -> str:
        if self.media_type == self.WEBP_MEDIA_TYPE:
            return self.WEBP_FORMAT
        return self.JPEG_FORMAT
