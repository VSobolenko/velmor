from __future__ import annotations

import io

from PIL import Image

from packages.services.src.commerce.errors import PreviewNotRenderableError


class ImagePayload:
    """The one place that decides whether origin bytes can become a preview.

    Publication and the preview cut both ask this class, so the two cannot
    disagree about what "renderable" means. A second predicate - one in the
    publication path and one in the derivative - would drift, and a payload one
    accepted would become a catalogue entry whose preview the other refuses for
    as long as the entry exists.

    ``MAX_DECODE_PIXELS`` is the bound the preview path already applied: an image
    whose header declares more pixels than this is refused before it is decoded,
    so a crafted header cannot make the process allocate a frame it cannot hold.
    """

    MAX_DECODE_PIXELS = 64_000_000
    NOT_RENDERABLE_REASON = 'the origin payload cannot be rendered as a preview'

    @classmethod
    def frame(cls, body: bytes) -> Image.Image:
        """The decoded frame for ``body``, or a typed refusal.

        Pillow documents that ``Image.open`` raises ``UnidentifiedImageError``, an
        ``OSError`` subclass, when "the image cannot be opened and identified"
        (Pillow reference, Image module), and raises ``OSError`` for a payload
        truncated while decoding. It also raises ``DecompressionBombError``, a
        plain ``Exception``, when an image declares more than twice
        ``Image.MAX_IMAGE_PIXELS``; that class is named separately because it is
        not an ``OSError``. The contract makes every one of them a refusal -
        publication refuses the good and a preview request falls back to the
        storefront's own placeholder - so translating them is the logic here
        rather than a catch that hides a failure. No predicate answers "is this a
        decodable image" without attempting the decode, and sniffing magic bytes
        by hand would refuse formats Pillow handles.

        Two catches, two authorizations. The ``DecompressionBombError`` and
        ``OSError`` pair is the catch ``PreviewDerivative.encode`` carried before
        the decode moved here, moved without widening (rule 03: an existing
        catch is grandfathered by the move, not by a neighbour). ``can_render``
        below states its own authorization for its catch.
        """
        try:
            with Image.open(io.BytesIO(body)) as opened:
                if opened.width * opened.height > cls.MAX_DECODE_PIXELS:
                    raise PreviewNotRenderableError(cls.NOT_RENDERABLE_REASON)
                # copy() decodes, so a truncated payload raises OSError here
                # rather than when a caller touches the frame, and the returned
                # image is detached from the BytesIO that is closed on exit.
                return opened.copy()
        except Image.DecompressionBombError as error:
            raise PreviewNotRenderableError(cls.NOT_RENDERABLE_REASON) from error
        except OSError as error:
            raise PreviewNotRenderableError(cls.NOT_RENDERABLE_REASON) from error

    @classmethod
    def can_render(cls, body: bytes) -> bool:
        """Whether ``body`` can become a preview, as a value.

        Authorized catch (rule 03 case 3, and ``design.md`` D2): the publication
        contract is that a good whose payload cannot be rendered is refused,
        rather than the whole ``velmor publish`` pass aborting at that good, so
        the typed refusal has to become ``False`` here instead of propagating.
        Alternatives ruled out: letting ``PreviewNotRenderableError`` propagate
        ends the pass at the first such good where the contract asks for one
        refusal; returning ``None`` from the decode would push the same branching
        onto every caller and give ``None`` a second meaning in a codebase where
        it marks a real absence. The exception is ours and specific, it carries
        the one reason, and the translation is what produces the value the
        contract asks for.
        """
        try:
            cls.frame(body)
        except PreviewNotRenderableError:
            return False
        return True
