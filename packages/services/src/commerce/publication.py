from __future__ import annotations

from datetime import datetime
from typing import Protocol

from packages.core.src.errors import RightsDeniedError
from packages.services.src.commerce.errors import (
    CategoryNotFoundError,
    DigestUnavailableError,
    PublicationSourceMismatchError,
)
from packages.services.src.commerce.image_payload import ImagePayload
from packages.services.src.commerce.slugs import ProductSlug
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.digest import DigestResult
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.publication import PublicationAction, PublicationOutcome
from packages.services.src.domain.source import SourceSpec
from packages.services.src.persistence.contract import (
    CatalogueEntryRepository,
    CategoryRepository,
)
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.src.saleor.client import SaleorProduct, SaleorVariant

DIGITAL_PRODUCT_TYPE_NAME: str = 'Digital good'


class SaleorPublicationPort(Protocol):
    """The Saleor operations the publication bridge uses."""

    async def ensure_product_type(self, name: str) -> str: ...

    async def create_product(
        self, name: str, slug: str, product_type_id: str, category_id: str | None
    ) -> SaleorProduct: ...

    async def update_product(
        self, product_id: str, name: str, slug: str, category_id: str | None
    ) -> SaleorProduct: ...

    async def create_variant(self, product_id: str, sku: str) -> SaleorVariant: ...

    async def update_variant(self, variant_id: str, sku: str) -> SaleorVariant: ...


class ContentDigestPort(Protocol):
    """Obtain an origin content digest for a publishable candidate."""

    async def obtain(self, download_url: str) -> DigestResult: ...


class PublicationBridge:
    """Turn a settled gate decision into a paid catalogue entry, or withdraw one.

    The bridge re-derives the gate's ruling from the decision's own record and
    never trusts the caller's ``publishable`` flag: a caller that asserts a
    ruling the gate does not produce is refused with ``RightsDeniedError``,
    while a decision that states the good is not publishable is an outcome the
    bridge handles. It does not assign categories or delete Saleor products on
    withdrawal. Every path that ends PUBLISHED obtains a content digest first;
    an unobtainable digest is a publication refusal, and so is a payload the
    platform cannot render, which also withdraws an entry that already
    advertises a preview the shop cannot produce.
    """

    def __init__(
        self,
        gate: PublicationGate,
        saleor: SaleorPublicationPort,
        entries: CatalogueEntryRepository,
        categories: CategoryRepository,
        digest: ContentDigestPort,
    ) -> None:
        self._gate = gate
        self._saleor = saleor
        self._entries = entries
        self._categories = categories
        self._digest = digest

    async def apply(
        self,
        candidate: Candidate,
        decision: GateDecision,
        spec: SourceSpec,
        now: datetime,
    ) -> PublicationOutcome:
        self._require_source_match(candidate, decision, spec)
        ruling = self._gate.decide(spec, decision.record)
        listing = self._gate.listing_for(decision.record)
        existing = await self._entries.by_candidate(candidate.id)

        if not decision.publishable:
            return await self._when_not_publishable(candidate, decision, existing)

        self._require_gate_approval(candidate, ruling)

        if listing is not StorefrontListing.PAID_OK:
            return await self._when_not_paid_ok(candidate, decision, listing, existing)

        return await self._when_paid_ok(candidate, decision, existing, now)

    def _require_gate_approval(self, candidate: Candidate, ruling: GateDecision) -> None:
        """Refuse a caller's assertion that the gate's own ruling contradicts.

        A decision that is not publishable is a normal outcome and takes the
        ``_when_not_publishable`` path. A decision that claims publishable while
        the gate refuses is not an outcome: the caller did not use the gate, so
        there is no entry to write and no reason to report against.
        """
        if ruling.publishable:
            return
        raise RightsDeniedError(
            f'{candidate.id!r} was presented as publishable but the gate refuses it: '
            f'{"; ".join(ruling.reasons)}'
        )

    def _require_source_match(
        self, candidate: Candidate, decision: GateDecision, spec: SourceSpec
    ) -> None:
        if candidate.source_id != spec.id or decision.record.source_id != spec.id:
            raise PublicationSourceMismatchError(
                f'candidate source {candidate.source_id!r} and decision source '
                f'{decision.record.source_id!r} must both equal spec {spec.id!r}'
            )

    async def _when_not_publishable(
        self,
        candidate: Candidate,
        decision: GateDecision,
        existing: CatalogueEntry | None,
    ) -> PublicationOutcome:
        if existing is None:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.REFUSED,
                reasons=decision.reasons,
                entry=None,
            )
        if existing.state is CatalogueEntryState.WITHDRAWN:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.UNCHANGED,
                reasons=('catalogue already matches: entry is withdrawn',),
                entry=existing,
            )
        reason = f'decision is not publishable: {"; ".join(decision.reasons)}'
        return await self._withdraw(candidate, existing, reason)

    async def _when_not_paid_ok(
        self,
        candidate: Candidate,
        decision: GateDecision,
        listing: StorefrontListing,
        existing: CatalogueEntry | None,
    ) -> PublicationOutcome:
        listing_reason = f'listing is not PAID_OK (listing={listing.value})'
        if existing is None:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.REFUSED,
                reasons=(listing_reason,),
                entry=None,
            )
        if existing.state is CatalogueEntryState.WITHDRAWN:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.UNCHANGED,
                reasons=('catalogue already matches: entry is withdrawn',),
                entry=existing,
            )
        return await self._withdraw(candidate, existing, listing_reason)

    async def _when_paid_ok(
        self,
        candidate: Candidate,
        decision: GateDecision,
        existing: CatalogueEntry | None,
        now: datetime,
    ) -> PublicationOutcome:
        digest_or_refusal = await self._digest_for_publish(candidate)
        if isinstance(digest_or_refusal, PublicationOutcome):
            return digest_or_refusal
        if not digest_or_refusal.renderable:
            return await self._when_not_renderable(candidate, existing)
        if existing is None:
            return await self._create_published(
                candidate, decision, now, digest_or_refusal
            )
        if existing.state is CatalogueEntryState.WITHDRAWN:
            return await self._re_publish(
                candidate, decision, existing, digest_or_refusal
            )
        return await self._update_published(
            candidate, decision, existing, digest_or_refusal
        )

    async def _when_not_renderable(
        self, candidate: Candidate, existing: CatalogueEntry | None
    ) -> PublicationOutcome:
        """Refuse an unrenderable payload, or withdraw the entry advertising it.

        The reason is built from ``ImagePayload``'s constant rather than written
        again here, so the message an operator reads cannot drift from the check
        that produced it. An entry whose payload cannot be rendered is one the
        shop cannot show, so leaving it published is the defect this change
        removes; a fetch failure is a different statement about a different thing
        and is handled in ``_digest_for_publish`` without withdrawing anything.
        """
        reason = ImagePayload.NOT_RENDERABLE_REASON
        if existing is None:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.REFUSED,
                reasons=(reason,),
                entry=None,
            )
        if existing.state is CatalogueEntryState.WITHDRAWN:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.UNCHANGED,
                reasons=(f'{reason}; catalogue already matches: entry is withdrawn',),
                entry=existing,
            )
        return await self._withdraw(candidate, existing, reason)

    async def _digest_for_publish(
        self, candidate: Candidate
    ) -> DigestResult | PublicationOutcome:
        if candidate.download_url is None:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.REFUSED,
                reasons=('no download URL is available for a digest',),
                entry=None,
            )
        # Authorized catch (rule 03 case 3): catalog-publication requires an
        # outcome for every operation. DigestUnavailableError is the typed
        # domain signal that the digest could not be obtained; translating it
        # into REFUSED *is* the refusal logic, not a transport catch. httpx
        # RequestError stays inside ContentDigest.
        try:
            return await self._digest.obtain(candidate.download_url)
        except DigestUnavailableError as error:
            return PublicationOutcome(
                candidate_id=candidate.id,
                action=PublicationAction.REFUSED,
                reasons=(str(error),),
                entry=None,
            )

    async def _create_published(
        self,
        candidate: Candidate,
        decision: GateDecision,
        now: datetime,
        digest: DigestResult,
    ) -> PublicationOutcome:
        slug = ProductSlug.for_candidate(candidate.id)
        sku = self._sku_for(candidate.id)
        product_type_id = await self._saleor.ensure_product_type(DIGITAL_PRODUCT_TYPE_NAME)
        product = await self._saleor.create_product(
            name=candidate.title,
            slug=slug,
            product_type_id=product_type_id,
            category_id=None,
        )
        variant = await self._saleor.create_variant(product_id=product.product_id, sku=sku)
        entry = CatalogueEntry(
            candidate_id=candidate.id,
            source_id=candidate.source_id,
            saleor_product_id=product.product_id,
            saleor_variant_id=variant.variant_id,
            category_id=None,
            license_id=decision.record.license_id,
            obligations=decision.record.obligations,
            listing=StorefrontListing.PAID_OK,
            state=CatalogueEntryState.PUBLISHED,
            withdrawal_reason=None,
            published_at=now,
            content_digest=digest.digest,
            origin_url=candidate.download_url,
        )
        await self._entries.save_entry(entry)
        return PublicationOutcome(
            candidate_id=candidate.id,
            action=PublicationAction.PUBLISHED,
            reasons=(),
            entry=entry,
        )

    async def _re_publish(
        self,
        candidate: Candidate,
        decision: GateDecision,
        existing: CatalogueEntry,
        digest: DigestResult,
    ) -> PublicationOutcome:
        slug = ProductSlug.for_candidate(candidate.id)
        sku = self._sku_for(candidate.id)
        saleor_category_id = await self._saleor_category_id_for(existing)
        await self._saleor.update_product(
            product_id=existing.saleor_product_id,
            name=candidate.title,
            slug=slug,
            category_id=saleor_category_id,
        )
        await self._saleor.update_variant(variant_id=existing.saleor_variant_id, sku=sku)
        entry = CatalogueEntry(
            candidate_id=candidate.id,
            source_id=candidate.source_id,
            saleor_product_id=existing.saleor_product_id,
            saleor_variant_id=existing.saleor_variant_id,
            category_id=existing.category_id,
            license_id=decision.record.license_id,
            obligations=decision.record.obligations,
            listing=StorefrontListing.PAID_OK,
            state=CatalogueEntryState.PUBLISHED,
            withdrawal_reason=None,
            published_at=existing.published_at,
            content_digest=digest.digest,
            origin_url=candidate.download_url,
        )
        await self._entries.save_entry(entry)
        return PublicationOutcome(
            candidate_id=candidate.id,
            action=PublicationAction.PUBLISHED,
            reasons=(),
            entry=entry,
        )

    async def _update_published(
        self,
        candidate: Candidate,
        decision: GateDecision,
        existing: CatalogueEntry,
        digest: DigestResult,
    ) -> PublicationOutcome:
        slug = ProductSlug.for_candidate(candidate.id)
        sku = self._sku_for(candidate.id)
        saleor_category_id = await self._saleor_category_id_for(existing)
        await self._saleor.update_product(
            product_id=existing.saleor_product_id,
            name=candidate.title,
            slug=slug,
            category_id=saleor_category_id,
        )
        await self._saleor.update_variant(variant_id=existing.saleor_variant_id, sku=sku)
        entry = CatalogueEntry(
            candidate_id=candidate.id,
            source_id=candidate.source_id,
            saleor_product_id=existing.saleor_product_id,
            saleor_variant_id=existing.saleor_variant_id,
            category_id=existing.category_id,
            license_id=decision.record.license_id,
            obligations=decision.record.obligations,
            listing=StorefrontListing.PAID_OK,
            state=CatalogueEntryState.PUBLISHED,
            withdrawal_reason=None,
            published_at=existing.published_at,
            content_digest=digest.digest,
            origin_url=candidate.download_url,
        )
        await self._entries.save_entry(entry)
        return PublicationOutcome(
            candidate_id=candidate.id,
            action=PublicationAction.UPDATED,
            reasons=(),
            entry=entry,
        )

    async def _withdraw(
        self, candidate: Candidate, existing: CatalogueEntry, reason: str
    ) -> PublicationOutcome:
        entry = CatalogueEntry(
            candidate_id=existing.candidate_id,
            source_id=existing.source_id,
            saleor_product_id=existing.saleor_product_id,
            saleor_variant_id=existing.saleor_variant_id,
            category_id=existing.category_id,
            license_id=existing.license_id,
            obligations=existing.obligations,
            listing=existing.listing,
            state=CatalogueEntryState.WITHDRAWN,
            withdrawal_reason=reason,
            published_at=existing.published_at,
            content_digest=existing.content_digest,
            origin_url=existing.origin_url,
        )
        await self._entries.save_entry(entry)
        return PublicationOutcome(
            candidate_id=candidate.id,
            action=PublicationAction.WITHDRAWN,
            reasons=(reason,),
            entry=entry,
        )

    async def _saleor_category_id_for(self, existing: CatalogueEntry) -> str | None:
        """Map a Velmor category id on the entry to Saleor's category id.

        ``CatalogueEntry.category_id`` is our id; Saleor ``update_product`` needs
        theirs. A missing category row is a defect in stored data, not a reason
        to invent an id or to pass ours on the wire.
        """
        if existing.category_id is None:
            return None
        category = await self._categories.by_id(existing.category_id)
        if category is None:
            raise CategoryNotFoundError(
                f'category {existing.category_id!r} was not found'
            )
        return category.saleor_category_id

    @staticmethod
    def _sku_for(candidate_id: str) -> str:
        # Deterministic from candidate.id so a title rename cannot orphan the SKU.
        # Colons in source-qualified ids are replaced so the SKU stays printable.
        safe = candidate_id.replace(':', '-').lower()
        return f'sku-{safe}'
