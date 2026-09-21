from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from packages.services.src.commerce.derivative import PreviewDerivative
from packages.services.src.commerce.errors import (
    CatalogueEntryNotFoundError,
    CoverRefusedError,
)
from packages.services.src.domain.catalogue import SaleableEntry
from packages.services.src.domain.preview import CatalogueCover, CoverSource
from packages.services.src.persistence.contract import (
    CatalogueCoverRepository,
    CatalogueEntryRepository,
)


class CoverAttacher:
    """Attach an operator-supplied cover to a catalogued good.

    A cover is presentation. It is served in place of a preview when a good has
    no usable image of its own, it never substitutes for the good at delivery,
    and attaching one changes nothing about what may be sold: the cover row is
    only reachable through the preview endpoint, which still refuses a good the
    catalogue does not hold as saleable.

    The bytes the operator supplies are cut to the same bounded derivative a
    preview uses and kept in the same cache, located by the digest of the file
    that was supplied rather than by a path of its own. Re-encoding is what makes
    a cover web-sized: the tool the cover comes from has no reason to be, and an
    unbounded PNG on a catalogue card is the problem the derivative exists to
    solve.
    """

    def __init__(
        self,
        entries: CatalogueEntryRepository,
        covers: CatalogueCoverRepository,
        derivative: PreviewDerivative,
        clock: Callable[[], datetime],
    ) -> None:
        self._entries = entries
        self._covers = covers
        self._derivative = derivative
        self._clock = clock

    async def attach(
        self,
        candidate_id: str,
        path: Path,
        source: CoverSource,
        rights_note: str,
    ) -> CatalogueCover:
        await self._require_saleable_entry(candidate_id)
        if rights_note.strip() == '':
            raise CoverRefusedError(
                'a cover needs the licence note that permits us to show it'
            )
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        self._derivative.cut(digest, body)
        cover = CatalogueCover(
            candidate_id=candidate_id,
            digest=digest,
            media_type=self._derivative.media_type,
            source=source,
            rights_note=rights_note,
            attached_at=self._clock(),
        )
        await self._covers.save_cover(cover)
        return cover

    async def attached(self) -> tuple[CatalogueCover, ...]:
        return await self._covers.all_covers()

    async def _require_saleable_entry(self, candidate_id: str) -> None:
        entry = await self._entries.by_candidate(candidate_id)
        if entry is None or not SaleableEntry.matches(entry):
            raise CatalogueEntryNotFoundError(
                f'catalogue entry for candidate {candidate_id!r} is not for sale'
            )
