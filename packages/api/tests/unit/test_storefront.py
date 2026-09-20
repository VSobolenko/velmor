from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from packages.api.src.app import ApiApplication, StorefrontPage
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate, build_record

Good = tuple[Candidate, RightsRecord]

_GRANT_SECRET = SecretStr('storefront-unit-grant-secret')
_NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


class FakeCatalog:
    """A catalogue holding a fixed set of goods, as the store would return."""

    def __init__(self, goods: tuple[Good, ...] = (), total: int | None = None) -> None:
        self._goods = goods
        self._total = len(goods) if total is None else total
        self.limits: list[int] = []

    async def published(self, limit: int) -> tuple[Good, ...]:
        self.limits.append(limit)
        return self._goods[:limit]

    async def published_count(self) -> int:
        return self._total


def build_client(
    goods: tuple[Good, ...] = (), total: int | None = None
) -> tuple[TestClient, FakeCatalog]:
    catalog = FakeCatalog(goods, total)
    store = InMemoryStore()
    cache = AssetCache(root=Path('var/test-storefront-cache'), max_bytes=1024)
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(404))
    )
    delivery = DeliveryService(
        entitlements=store, entries=store, cache=cache, http=http
    )
    grants = DeliveryGrantService(secret=_GRANT_SECRET, lifetime_seconds=900)
    app = ApiApplication(
        'test',
        catalog,
        grants=grants,
        delivery=delivery,
        entitlements=store,
        clock=lambda: _NOW,
    ).build()
    return TestClient(app), catalog


def build_good(**overrides: object) -> Good:
    candidate = build_candidate()
    record = build_record()
    if 'title' in overrides:
        candidate = candidate.model_copy(update={'title': overrides['title']})
    if 'landing_url' in overrides:
        candidate = candidate.model_copy(update={'landing_url': overrides['landing_url']})
    if 'obligations' in overrides:
        record = record.model_copy(update={'obligations': overrides['obligations']})
    return candidate, record


class TestStorefront:
    def test_a_published_good_is_listed_with_its_licence(self) -> None:
        client, _ = build_client((build_good(),))

        response = client.get('/')

        assert response.status_code == 200
        assert 'Sample good' in response.text
        assert 'CC-BY-4.0' in response.text
        assert 'allowed' in response.text

    def test_obligations_are_stated_so_a_buyer_knows_them(self) -> None:
        good = build_good(obligations=('Credit the creator',))
        client, _ = build_client((good,))

        response = client.get('/')

        assert 'Credit the creator' in response.text

    def test_a_third_party_title_cannot_inject_markup(self) -> None:
        client, _ = build_client((build_good(title='<script>alert(1)</script>'),))

        response = client.get('/')

        assert '<script>alert(1)</script>' not in response.text
        assert '&lt;script&gt;alert(1)&lt;/script&gt;' in response.text

    def test_a_quote_in_a_url_cannot_escape_its_attribute(self) -> None:
        hostile = 'https://x.test/item" onmouseover="alert(1)'
        client, _ = build_client((build_good(landing_url=hostile),))

        response = client.get('/')

        assert hostile not in response.text
        assert '&quot;' in response.text

    def test_an_empty_catalogue_says_so(self) -> None:
        client, _ = build_client()

        response = client.get('/')

        assert StorefrontPage.EMPTY in response.text
        assert '0 approved for sale' in response.text

    def test_every_good_gets_its_own_card(self) -> None:
        goods = tuple(
            (build_candidate(candidate_id=f'openverse:{index}'), build_record())
            for index in range(3)
        )
        client, _ = build_client(goods)

        response = client.get('/')

        assert response.text.count('<article class="card">') == 3
        assert '3 approved for sale' in response.text

    def test_the_catalogue_query_is_bounded(self) -> None:
        client, catalog = build_client()

        client.get('/')

        assert catalog.limits == [ApiApplication.CATALOGUE_LIMIT]

    def test_a_truncated_page_does_not_pass_the_cap_off_as_the_total(self) -> None:
        """The count is the business's, not the page size."""
        goods = tuple(
            (build_candidate(candidate_id=f'openverse:{index}'), build_record())
            for index in range(3)
        )
        client, _ = build_client(goods, total=105)

        response = client.get('/')

        assert '105 approved for sale, showing the 3 most recent' in response.text
        assert response.text.count('<article class="card">') == 3

    def test_a_complete_page_states_the_total_without_qualification(self) -> None:
        client, _ = build_client((build_good(),))

        response = client.get('/')

        assert '1 approved for sale' in response.text
        assert 'showing' not in response.text

    def test_health_reports_the_environment(self) -> None:
        client, _ = build_client()

        response = client.get('/health')

        assert response.status_code == 200
        assert response.json() == {'status': 'ok', 'environment': 'test'}
