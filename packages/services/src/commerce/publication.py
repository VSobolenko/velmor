from __future__ import annotations

from datetime import datetime
from typing import Protocol

from packages.services.src.commerce.errors import PublicationSourceMismatchError
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.publication import PublicationAction, PublicationOutcome
from packages.services.src.domain.source import SourceSpec
from packages.services.src.persistence.contract import CatalogueEntryRepository
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


class PublicationBridge:
    """Turn a settled gate decision into a paid catalogue entry, or withdraw one.

    The bridge consults ``PublicationGate.listing_for`` and never calls
    ``decide``: publishability is an input. It does not download content, assign
    categories, or delete Saleor products on withdrawal.
    """

    def __init__(
        self,
        gate: PublicationGate,
        saleor: SaleorPublicationPort,
        entries: CatalogueEntryRepository,
    ) -> None:
        self._gate = gate
        self._saleor = saleor
        self._entries = entries

    async def apply(
        self,
        candidate: Candidate,
        decision: GateDecision,
        spec: SourceSpec,
        now: datetime,
    ) -> PublicationOutcome:
        self._require_source_match(candidate, decision, spec)
        listing = self._gate.listing_for(decision.record)
        existing = await self._entries.by_candidate(candidate.id)

        if not decision.publishable:
            return await self._when_not_publishable(candidate, decision, existing)

        if listing is not StorefrontListing.PAID_OK:
            return await self._when_not_paid_ok(candidate, decision, listing, existing)

        return await self._when_paid_ok(candidate, decision, existing, now)

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
        if existing is None:
            return await self._create_published(candidate, decision, now)
        if existing.state is CatalogueEntryState.WITHDRAWN:
            return await self._re_publish(candidate, decision, existing)
        return await self._update_published(candidate, decision, existing)

    async def _create_published(
        self, candidate: Candidate, decision: GateDecision, now: datetime
    ) -> PublicationOutcome:
        slug = self._slug_for(candidate.id)
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
    ) -> PublicationOutcome:
        slug = self._slug_for(candidate.id)
        sku = self._sku_for(candidate.id)
        await self._saleor.update_product(
            product_id=existing.saleor_product_id,
            name=candidate.title,
            slug=slug,
            category_id=existing.category_id,
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
    ) -> PublicationOutcome:
        slug = self._slug_for(candidate.id)
        sku = self._sku_for(candidate.id)
        await self._saleor.update_product(
            product_id=existing.saleor_product_id,
            name=candidate.title,
            slug=slug,
            category_id=existing.category_id,
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
        )
        await self._entries.save_entry(entry)
        return PublicationOutcome(
            candidate_id=candidate.id,
            action=PublicationAction.WITHDRAWN,
            reasons=(reason,),
            entry=entry,
        )

    @staticmethod
    def _slug_for(candidate_id: str) -> str:
        # Deterministic from candidate.id so a title rename cannot orphan the slug.
        return f'good-{candidate_id}'.lower()

    @staticmethod
    def _sku_for(candidate_id: str) -> str:
        # Deterministic from candidate.id so a title rename cannot orphan the SKU.
        return f'sku-{candidate_id}'.lower()
