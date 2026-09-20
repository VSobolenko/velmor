from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.services.src.commerce.publication import (
    PublicationBridge,
    PublicationSourceMismatchError,
)
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.publication import PublicationAction, PublicationOutcome
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.domain.source import SourceSpec
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.src.saleor.client import SaleorProduct, SaleorVariant
from packages.services.tests.conftest import build_candidate, build_record, build_spec

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)

PAID_OBLIGATIONS: tuple[str, ...] = (
    'Credit the creator',
    'Link to the license text',
    'Indicate whether changes were made',
)


class FakeSaleor:
    """Records Saleor calls and returns stable product and variant ids."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self._product_seq = 0
        self._variant_seq = 0

    async def ensure_product_type(self, name: str) -> str:
        self.calls.append(('ensure_product_type', name))
        return 'product-type-digital'

    async def create_product(
        self, name: str, slug: str, product_type_id: str, category_id: str | None
    ) -> SaleorProduct:
        self.calls.append(('create_product', name, slug, product_type_id, category_id))
        self._product_seq += 1
        return SaleorProduct(product_id=f'product-{self._product_seq}')

    async def update_product(
        self, product_id: str, name: str, slug: str, category_id: str | None
    ) -> SaleorProduct:
        self.calls.append(('update_product', product_id, name, slug, category_id))
        return SaleorProduct(product_id=product_id)

    async def create_variant(self, product_id: str, sku: str) -> SaleorVariant:
        self.calls.append(('create_variant', product_id, sku))
        self._variant_seq += 1
        return SaleorVariant(variant_id=f'variant-{self._variant_seq}')

    async def update_variant(self, variant_id: str, sku: str) -> SaleorVariant:
        self.calls.append(('update_variant', variant_id, sku))
        return SaleorVariant(variant_id=variant_id)


def paid_record(
    license_id: str = 'CC-BY-4.0',
    obligations: tuple[str, ...] = PAID_OBLIGATIONS,
) -> RightsRecord:
    return build_record(license_id=license_id).model_copy(update={'obligations': obligations})


def free_only_record() -> RightsRecord:
    return build_record(license_id='GPL-3.0-only').model_copy(
        update={'obligations': ('Provide the complete corresponding source',)}
    )


def denied_record() -> RightsRecord:
    return build_record(license_id=None, verdict='denied')


def publishable_decision(record: RightsRecord | None = None) -> GateDecision:
    body = record if record is not None else paid_record()
    return GateDecision(
        candidate_id=body.candidate_id,
        publishable=True,
        reasons=(),
        record=body,
    )


def refused_decision(
    reasons: tuple[str, ...] = ('Rights verdict is denied: built for test',),
    record: RightsRecord | None = None,
) -> GateDecision:
    body = record if record is not None else denied_record()
    return GateDecision(
        candidate_id=body.candidate_id,
        publishable=False,
        reasons=reasons,
        record=body,
    )


def published_entry(
    candidate_id: str = 'openverse:1',
    source_id: str = 'openverse',
    published_at: datetime = EARLIER,
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id=source_id,
        saleor_product_id='product-existing',
        saleor_variant_id='variant-existing',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=PAID_OBLIGATIONS,
        listing=StorefrontListing.PAID_OK,
        state=CatalogueEntryState.PUBLISHED,
        withdrawal_reason=None,
        published_at=published_at,
    )


def withdrawn_entry(
    candidate_id: str = 'openverse:1',
    reason: str = 'previously withdrawn',
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id='openverse',
        saleor_product_id='product-existing',
        saleor_variant_id='variant-existing',
        category_id=None,
        license_id='CC-BY-4.0',
        obligations=PAID_OBLIGATIONS,
        listing=StorefrontListing.PAID_OK,
        state=CatalogueEntryState.WITHDRAWN,
        withdrawal_reason=reason,
        published_at=EARLIER,
    )


@pytest.fixture
def saleor() -> FakeSaleor:
    return FakeSaleor()


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def bridge(gate: PublicationGate, saleor: FakeSaleor, store: InMemoryStore) -> PublicationBridge:
    return PublicationBridge(gate=gate, saleor=saleor, entries=store)


@pytest.fixture
def spec() -> SourceSpec:
    return build_spec()


@pytest.fixture
def candidate() -> Candidate:
    return build_candidate()


class TestPublicationBridge:
    async def test_happy_publish_creates_a_paid_entry(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        decision = publishable_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.PUBLISHED
        assert outcome.reasons == ()
        assert outcome.candidate_id == candidate.id
        assert outcome.entry is not None
        assert outcome.entry.state is CatalogueEntryState.PUBLISHED
        assert outcome.entry.listing is StorefrontListing.PAID_OK
        assert outcome.entry.saleor_product_id == 'product-1'
        assert outcome.entry.saleor_variant_id == 'variant-1'
        assert outcome.entry.license_id == decision.record.license_id
        assert outcome.entry.obligations == decision.record.obligations
        assert outcome.entry.published_at == NOW
        assert outcome.entry.withdrawal_reason is None
        assert outcome.entry.category_id is None
        assert await store.by_candidate(candidate.id) == outcome.entry
        assert [call[0] for call in saleor.calls] == [
            'ensure_product_type',
            'create_product',
            'create_variant',
        ]
        assert not any(call[0].startswith('update_') for call in saleor.calls)

    async def test_idempotent_re_publish_updates_without_duplicating(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        decision = publishable_decision()

        first = await bridge.apply(candidate, decision, spec, NOW)
        saleor.calls.clear()
        second = await bridge.apply(candidate, decision, spec, NOW)

        assert first.action is PublicationAction.PUBLISHED
        assert second.action is PublicationAction.UPDATED
        assert second.reasons == ()
        assert len(await store.entries(10)) == 1
        assert [call[0] for call in saleor.calls] == ['update_product', 'update_variant']
        assert not any(call[0] == 'create_product' for call in saleor.calls)
        assert second.entry is not None
        assert second.entry.published_at == NOW
        assert second.entry.saleor_product_id == first.entry.saleor_product_id
        assert second.entry.saleor_variant_id == first.entry.saleor_variant_id

    async def test_not_publishable_with_no_entry_is_refused(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        decision = refused_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.REFUSED
        assert outcome.reasons == decision.reasons
        assert outcome.entry is None
        assert await store.by_candidate(candidate.id) is None
        assert saleor.calls == []

    async def test_not_publishable_withdraws_a_published_entry(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        await store.save_entry(published_entry())
        decision = refused_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.WITHDRAWN
        assert outcome.entry is not None
        assert outcome.entry.state is CatalogueEntryState.WITHDRAWN
        assert outcome.entry.withdrawal_reason is not None
        assert outcome.reasons != ()
        assert await store.by_candidate(candidate.id) == outcome.entry
        assert saleor.calls == []

    async def test_free_only_with_no_entry_is_refused(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
        gate: PublicationGate,
    ) -> None:
        record = free_only_record()
        assert gate.listing_for(record) is StorefrontListing.FREE_ONLY
        decision = publishable_decision(record)

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.REFUSED
        assert outcome.entry is None
        assert await store.by_candidate(candidate.id) is None
        assert saleor.calls == []
        assert len(outcome.reasons) == 1
        reason = outcome.reasons[0]
        assert 'PAID_OK' in reason
        assert StorefrontListing.FREE_ONLY.value in reason

    async def test_free_only_withdraws_a_published_entry(
        self,
        bridge: PublicationBridge,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        await store.save_entry(published_entry())
        decision = publishable_decision(free_only_record())

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.WITHDRAWN
        assert outcome.entry is not None
        assert outcome.entry.state is CatalogueEntryState.WITHDRAWN
        assert outcome.entry.withdrawal_reason is not None

    async def test_already_withdrawn_and_still_refused_is_unchanged(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        existing = withdrawn_entry()
        await store.save_entry(existing)
        decision = refused_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.UNCHANGED
        assert outcome.reasons != ()
        assert outcome.entry is not None
        assert outcome.entry.state is CatalogueEntryState.WITHDRAWN
        assert outcome.entry.withdrawal_reason == existing.withdrawal_reason
        assert saleor.calls == []

    async def test_re_publish_after_withdrawal_restores_published_entry(
        self,
        bridge: PublicationBridge,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        await store.save_entry(withdrawn_entry())
        decision = publishable_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.PUBLISHED
        assert outcome.entry is not None
        assert outcome.entry.state is CatalogueEntryState.PUBLISHED
        assert outcome.entry.withdrawal_reason is None
        assert outcome.entry.listing is StorefrontListing.PAID_OK

    async def test_source_mismatch_raises_without_side_effects(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
    ) -> None:
        other_spec = build_spec(source_id='other-source')
        decision = publishable_decision()

        with pytest.raises(PublicationSourceMismatchError):
            await bridge.apply(candidate, decision, other_spec, NOW)

        assert saleor.calls == []
        assert await store.by_candidate(candidate.id) is None

    async def test_provenance_survives_publication(
        self,
        bridge: PublicationBridge,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        decision = publishable_decision(
            paid_record(license_id='CC-BY-4.0', obligations=PAID_OBLIGATIONS)
        )

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.entry is not None
        assert outcome.entry.license_id == decision.record.license_id
        assert outcome.entry.obligations == decision.record.obligations
        assert outcome.entry.candidate_id == candidate.id
        assert outcome.entry.source_id == candidate.source_id

    async def test_publish_does_not_read_download_url(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        spec: SourceSpec,
    ) -> None:
        candidate = build_candidate()
        candidate.download_url = None
        decision = publishable_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.PUBLISHED
        assert outcome.entry is not None
        assert await store.by_candidate(candidate.id) is not None
        assert saleor.calls != []
        assert all(
            call[0]
            in {
                'ensure_product_type',
                'create_product',
                'create_variant',
                'update_product',
                'update_variant',
            }
            for call in saleor.calls
        )


class TestPublicationOutcomeModel:
    def test_outcome_is_frozen(self) -> None:
        outcome = PublicationOutcome(
            candidate_id='openverse:1',
            action=PublicationAction.REFUSED,
            reasons=('not publishable',),
            entry=None,
        )

        with pytest.raises(Exception):
            outcome.action = PublicationAction.PUBLISHED
