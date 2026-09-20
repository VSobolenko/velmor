from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.license import StorefrontListing

PUBLISHED_AT = datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc)
FIXTURE_DIGEST = '00' * 32


def build_entry(
    candidate_id: str = 'openverse:1',
    source_id: str = 'openverse',
    saleor_product_id: str = 'UHJvZHVjdDox',
    saleor_variant_id: str = 'UHJvZHVjdFZhcmlhbnQ6MQ==',
    category_id: str | None = None,
    license_id: str | None = 'CC-BY-4.0',
    obligations: tuple[str, ...] = ('credit the creator',),
    listing: StorefrontListing = StorefrontListing.PAID_OK,
    state: CatalogueEntryState = CatalogueEntryState.PUBLISHED,
    withdrawal_reason: str | None = None,
    published_at: datetime = PUBLISHED_AT,
    content_digest: str = FIXTURE_DIGEST,
    origin_url: str = 'https://origin.test/asset.bin',
) -> CatalogueEntry:
    return CatalogueEntry(
        candidate_id=candidate_id,
        source_id=source_id,
        saleor_product_id=saleor_product_id,
        saleor_variant_id=saleor_variant_id,
        category_id=category_id,
        license_id=license_id,
        obligations=obligations,
        listing=listing,
        state=state,
        withdrawal_reason=withdrawal_reason,
        published_at=published_at,
        content_digest=content_digest,
        origin_url=origin_url,
    )


class TestCatalogueEntryState:
    def test_the_state_values_are_the_strings_the_system_persists(self) -> None:
        assert CatalogueEntryState.PUBLISHED == 'published'
        assert CatalogueEntryState.WITHDRAWN == 'withdrawn'

    def test_there_are_exactly_two_states(self) -> None:
        assert set(CatalogueEntryState) == {
            CatalogueEntryState.PUBLISHED,
            CatalogueEntryState.WITHDRAWN,
        }


class TestCatalogueEntry:
    def test_an_entry_carries_its_provenance_and_published_decision(self) -> None:
        entry = build_entry()

        assert entry.candidate_id == 'openverse:1'
        assert entry.source_id == 'openverse'
        assert entry.saleor_product_id == 'UHJvZHVjdDox'
        assert entry.saleor_variant_id == 'UHJvZHVjdFZhcmlhbnQ6MQ=='
        assert entry.license_id == 'CC-BY-4.0'
        assert entry.listing is StorefrontListing.PAID_OK
        assert entry.state is CatalogueEntryState.PUBLISHED
        assert entry.published_at == PUBLISHED_AT
        assert entry.content_digest == FIXTURE_DIGEST
        assert entry.origin_url == 'https://origin.test/asset.bin'

    def test_the_optional_fields_default_to_none(self) -> None:
        entry = CatalogueEntry(
            candidate_id='openverse:1',
            source_id='openverse',
            saleor_product_id='UHJvZHVjdDox',
            saleor_variant_id='UHJvZHVjdFZhcmlhbnQ6MQ==',
            obligations=(),
            listing=StorefrontListing.PAID_OK,
            state=CatalogueEntryState.PUBLISHED,
            published_at=PUBLISHED_AT,
            content_digest=FIXTURE_DIGEST,
            origin_url='https://origin.test/asset.bin',
        )

        assert entry.category_id is None
        assert entry.license_id is None
        assert entry.withdrawal_reason is None

    def test_a_withdrawn_entry_reports_its_reason(self) -> None:
        entry = build_entry(
            state=CatalogueEntryState.WITHDRAWN,
            withdrawal_reason='the decision is no longer publishable',
        )

        assert entry.state is CatalogueEntryState.WITHDRAWN
        assert entry.withdrawal_reason == 'the decision is no longer publishable'

    def test_obligations_are_stored_as_a_tuple_in_order(self) -> None:
        entry = build_entry(obligations=['credit the creator', 'link the licence'])

        assert entry.obligations == ('credit the creator', 'link the licence')
        assert isinstance(entry.obligations, tuple)

    def test_a_missing_saleor_variant_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CatalogueEntry(
                candidate_id='openverse:1',
                source_id='openverse',
                saleor_product_id='UHJvZHVjdDox',
                obligations=(),
                listing=StorefrontListing.PAID_OK,
                state=CatalogueEntryState.PUBLISHED,
                published_at=PUBLISHED_AT,
            )

    def test_a_missing_listing_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CatalogueEntry(
                candidate_id='openverse:1',
                source_id='openverse',
                saleor_product_id='UHJvZHVjdDox',
                saleor_variant_id='UHJvZHVjdFZhcmlhbnQ6MQ==',
                obligations=(),
                state=CatalogueEntryState.PUBLISHED,
                published_at=PUBLISHED_AT,
            )


    def test_a_missing_content_digest_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CatalogueEntry(
                candidate_id='openverse:1',
                source_id='openverse',
                saleor_product_id='UHJvZHVjdDox',
                saleor_variant_id='UHJvZHVjdFZhcmlhbnQ6MQ==',
                obligations=(),
                listing=StorefrontListing.PAID_OK,
                state=CatalogueEntryState.PUBLISHED,
                published_at=PUBLISHED_AT,
                origin_url='https://origin.test/asset.bin',
            )

    def test_a_missing_origin_url_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CatalogueEntry(
                candidate_id='openverse:1',
                source_id='openverse',
                saleor_product_id='UHJvZHVjdDox',
                saleor_variant_id='UHJvZHVjdFZhcmlhbnQ6MQ==',
                obligations=(),
                listing=StorefrontListing.PAID_OK,
                state=CatalogueEntryState.PUBLISHED,
                published_at=PUBLISHED_AT,
                content_digest=FIXTURE_DIGEST,
            )

    def test_an_entry_is_frozen(self) -> None:
        entry = build_entry()

        with pytest.raises(ValidationError):
            entry.state = CatalogueEntryState.WITHDRAWN
