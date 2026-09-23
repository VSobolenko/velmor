from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.services.src.commerce.category_service import CategoryService
from packages.services.src.commerce.errors import CategoryNotFoundError
from packages.services.src.commerce.image_payload import ImagePayload
from packages.services.src.commerce.publication import (
    PublicationBridge,
    PublicationSourceMismatchError,
)
from packages.services.src.commerce.slugs import ProductSlug
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.category import CategoryName
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.presentation import Locale
from packages.services.src.domain.publication import PublicationAction, PublicationOutcome
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.domain.source import SourceSpec
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.src.saleor.client import SaleorCategory, SaleorProduct, SaleorVariant
from packages.services.tests.conftest import build_candidate, build_record, build_spec

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)

PAID_OBLIGATIONS: tuple[str, ...] = (
    'Credit the creator',
    'Link to the license text',
    'Indicate whether changes were made',
)

FIXTURE_DIGEST = '00' * 32
REAL_DIGEST = 'aa' * 32


class FakeDigest:
    """Records obtain calls and returns a configured result or raises."""

    def __init__(
        self,
        digest: str = REAL_DIGEST,
        *,
        renderable: bool = True,
        error: Exception | None = None,
    ) -> None:
        self.digest = digest
        self.renderable = renderable
        self.error = error
        self.urls: list[str] = []

    async def obtain(self, download_url: str):
        from packages.services.src.domain.digest import DigestResult

        self.urls.append(download_url)
        if self.error is not None:
            raise self.error
        return DigestResult(
            digest=self.digest,
            size_bytes=12,
            cached=False,
            renderable=self.renderable,
        )


class FakeSaleor:
    """Records Saleor calls and returns stable product and variant ids."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self._product_seq = 0
        self._variant_seq = 0
        self._category_seq = 0

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

    async def create_category(self, name: str, slug: str) -> SaleorCategory:
        self.calls.append(('create_category', name, slug))
        self._category_seq += 1
        return SaleorCategory(category_id=f'saleor-cat-{self._category_seq}')

    async def update_category(
        self, category_id: str, name: str, slug: str
    ) -> SaleorCategory:
        self.calls.append(('update_category', category_id, name, slug))
        return SaleorCategory(category_id=category_id)

    async def delete_category(self, category_id: str) -> None:
        self.calls.append(('delete_category', category_id))


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
        content_digest=FIXTURE_DIGEST,
        origin_url='https://openverse.test/items/openverse:1.bin',
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
        content_digest=FIXTURE_DIGEST,
        origin_url='https://openverse.test/items/openverse:1.bin',
    )


@pytest.fixture
def saleor() -> FakeSaleor:
    return FakeSaleor()


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def digest() -> FakeDigest:
    return FakeDigest()


@pytest.fixture
def bridge(
    gate: PublicationGate,
    saleor: FakeSaleor,
    store: InMemoryStore,
    digest: FakeDigest,
) -> PublicationBridge:
    return PublicationBridge(
        gate=gate, saleor=saleor, entries=store, categories=store, digest=digest
    )


def bridge_over_digest(
    gate: PublicationGate,
    saleor: FakeSaleor,
    store: InMemoryStore,
    digest: FakeDigest,
) -> PublicationBridge:
    """A bridge over a digest that answers renderability or failure deliberately."""
    return PublicationBridge(
        gate=gate, saleor=saleor, entries=store, categories=store, digest=digest
    )


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
        assert outcome.entry.content_digest == REAL_DIGEST
        assert outcome.entry.origin_url == candidate.download_url
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

    async def test_publish_without_download_url_is_refused(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        digest: FakeDigest,
        spec: SourceSpec,
    ) -> None:
        candidate = build_candidate()
        candidate.download_url = None
        decision = publishable_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.REFUSED
        assert outcome.entry is None
        assert await store.by_candidate(candidate.id) is None
        assert saleor.calls == []
        assert digest.urls == []
        assert any('download' in reason.lower() for reason in outcome.reasons)

    async def test_successful_publish_records_digest_and_calls_obtain(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        digest: FakeDigest,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        decision = publishable_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.PUBLISHED
        assert outcome.entry is not None
        assert outcome.entry.content_digest == REAL_DIGEST
        assert digest.urls == [candidate.download_url]
        assert any(call[0] == 'create_product' for call in saleor.calls)

    async def test_digest_unavailable_refuses_create(
        self,
        gate: PublicationGate,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        from packages.services.src.commerce.errors import DigestUnavailableError

        digest = FakeDigest(error=DigestUnavailableError('origin returned HTTP 500'))
        bridge = PublicationBridge(
            gate=gate, saleor=saleor, entries=store, categories=store, digest=digest
        )
        decision = publishable_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.REFUSED
        assert outcome.entry is None
        assert await store.by_candidate(candidate.id) is None
        assert saleor.calls == []
        assert digest.urls == [candidate.download_url]
        assert any('500' in reason or 'origin' in reason.lower() for reason in outcome.reasons)

    async def test_digest_unavailable_on_update_leaves_entry_unchanged(
        self,
        gate: PublicationGate,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        from packages.services.src.commerce.errors import DigestUnavailableError

        existing = published_entry()
        await store.save_entry(existing)
        digest = FakeDigest(error=DigestUnavailableError('origin returned HTTP 404'))
        bridge = PublicationBridge(
            gate=gate, saleor=saleor, entries=store, categories=store, digest=digest
        )
        decision = publishable_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.REFUSED
        assert saleor.calls == []
        assert await store.by_candidate(candidate.id) == existing
        assert any('404' in reason or 'origin' in reason.lower() for reason in outcome.reasons)

    async def test_rights_refused_skips_digest(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        digest: FakeDigest,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        decision = refused_decision()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.REFUSED
        assert digest.urls == []
        assert saleor.calls == []
        assert await store.by_candidate(candidate.id) is None

    async def test_update_after_assign_sends_saleor_category_id(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        decision = publishable_decision()
        published = await bridge.apply(candidate, decision, spec, NOW)
        assert published.entry is not None
        categories = CategoryService(categories=store, entries=store, saleor=saleor)
        category = await categories.create(
            name='Photographs',
            slug='photographs',
            names=(
                CategoryName(locale=Locale.RU, name='Фотографии'),
                CategoryName(locale=Locale.BE, name='Фатаграфіі'),
                CategoryName(locale=Locale.EN, name='Photographs'),
            ),
            now=NOW,
        )
        assert category.category_id == 'cat-photographs'
        assert category.saleor_category_id == 'saleor-cat-1'
        assert category.category_id != category.saleor_category_id
        await categories.assign(
            candidate_id=candidate.id,
            category_id=category.category_id,
            product_name=candidate.title,
        )
        saleor.calls.clear()

        outcome = await bridge.apply(candidate, decision, spec, NOW)

        assert outcome.action is PublicationAction.UPDATED
        assert outcome.entry is not None
        assert outcome.entry.category_id == category.category_id
        assert (
            'update_product',
            published.entry.saleor_product_id,
            candidate.title,
            ProductSlug.for_candidate(candidate.id),
            category.saleor_category_id,
        ) in saleor.calls
        assert not any(
            call[0] == 'update_product' and call[4] == category.category_id
            for call in saleor.calls
        )

    async def test_update_with_missing_category_raises(
        self,
        bridge: PublicationBridge,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        await store.save_entry(
            published_entry().model_copy(update={'category_id': 'cat-missing'})
        )
        decision = publishable_decision()

        with pytest.raises(CategoryNotFoundError):
            await bridge.apply(candidate, decision, spec, NOW)

        assert saleor.calls == []


class TestUnrenderablePayload:
    """A payload the platform cannot render: refuse, or withdraw what advertises it."""

    async def test_with_no_entry_the_good_is_refused_with_the_reason(
        self,
        gate: PublicationGate,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        bridge = bridge_over_digest(gate, saleor, store, FakeDigest(renderable=False))

        outcome = await bridge.apply(candidate, publishable_decision(), spec, NOW)

        assert outcome.action is PublicationAction.REFUSED
        assert outcome.entry is None
        assert await store.by_candidate(candidate.id) is None
        assert outcome.reasons != ()
        assert ImagePayload.NOT_RENDERABLE_REASON in outcome.reasons[0]
        assert candidate.download_url not in outcome.reasons[0]
        assert saleor.calls == []

    async def test_a_published_entry_is_withdrawn_with_the_reason(
        self,
        gate: PublicationGate,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        await store.save_entry(published_entry())
        bridge = bridge_over_digest(gate, saleor, store, FakeDigest(renderable=False))

        outcome = await bridge.apply(candidate, publishable_decision(), spec, NOW)

        assert outcome.action is PublicationAction.WITHDRAWN
        assert outcome.entry is not None
        assert outcome.entry.state is CatalogueEntryState.WITHDRAWN
        assert outcome.entry.withdrawal_reason is not None
        assert await store.by_candidate(candidate.id) == outcome.entry
        assert outcome.reasons != ()
        assert ImagePayload.NOT_RENDERABLE_REASON in outcome.reasons[0]
        assert candidate.download_url not in outcome.reasons[0]
        assert saleor.calls == []

    async def test_an_already_withdrawn_entry_is_unchanged(
        self,
        gate: PublicationGate,
        saleor: FakeSaleor,
        store: InMemoryStore,
        candidate: Candidate,
        spec: SourceSpec,
    ) -> None:
        existing = withdrawn_entry()
        await store.save_entry(existing)
        bridge = bridge_over_digest(gate, saleor, store, FakeDigest(renderable=False))

        outcome = await bridge.apply(candidate, publishable_decision(), spec, NOW)

        assert outcome.action is PublicationAction.UNCHANGED
        assert outcome.entry is not None
        assert outcome.entry.state is CatalogueEntryState.WITHDRAWN
        assert outcome.entry.withdrawal_reason == existing.withdrawal_reason
        assert outcome.reasons != ()
        assert ImagePayload.NOT_RENDERABLE_REASON in outcome.reasons[0]
        assert candidate.download_url not in outcome.reasons[0]
        assert saleor.calls == []

    async def test_unrenderable_withdraws_while_unobtainable_leaves_published(
        self,
        gate: PublicationGate,
        saleor: FakeSaleor,
        store: InMemoryStore,
        spec: SourceSpec,
    ) -> None:
        """The two refusal causes are distinguishable in one pass.

        A payload we cannot render is a fact about bytes we hold, so the entry
        that advertises it goes; an origin we cannot fetch is a statement about
        the origin, so the entry is left as it was.
        """
        from packages.services.src.commerce.errors import DigestUnavailableError

        await store.save_entry(published_entry(candidate_id='openverse:1'))
        await store.save_entry(published_entry(candidate_id='openverse:2'))
        unrenderable = bridge_over_digest(
            gate, saleor, store, FakeDigest(renderable=False)
        )
        unobtainable = bridge_over_digest(
            gate,
            saleor,
            store,
            FakeDigest(error=DigestUnavailableError('origin returned HTTP 404')),
        )

        withdrawn = await unrenderable.apply(
            build_candidate(candidate_id='openverse:1'), publishable_decision(), spec, NOW
        )
        refused = await unobtainable.apply(
            build_candidate(candidate_id='openverse:2'), publishable_decision(), spec, NOW
        )

        assert withdrawn.action is PublicationAction.WITHDRAWN
        assert refused.action is PublicationAction.REFUSED
        remained_withdrawn = await store.by_candidate('openverse:1')
        remained_published = await store.by_candidate('openverse:2')
        assert remained_withdrawn is not None
        assert remained_withdrawn.state is CatalogueEntryState.WITHDRAWN
        assert remained_published is not None
        assert remained_published.state is CatalogueEntryState.PUBLISHED


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
