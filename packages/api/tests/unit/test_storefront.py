from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.datastructures import DefaultPlaceholder
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import SecretStr

from packages.api.src.app import ApiApplication
from packages.api.tests.unit.storefront_services import build_catalogue, build_preview
from packages.services.src.commerce.asset_cache import AssetCache
from packages.services.src.commerce.checkout import CheckoutService
from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.catalogue import CatalogueEntry, CatalogueEntryState
from packages.services.src.domain.entitlement import Entitlement, EntitlementState
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.stripe_provider import StripeProvider
from packages.services.src.persistence.memory import InMemoryStore
from packages.services.tests.conftest import build_candidate
from packages.services.tests.unit.payments.test_bepaid_provider import (
    PUBLIC_KEY_PEM as BEPAID_PUBLIC_KEY_PEM,
)

CANDIDATE_ID = 'openverse:1'
DIGEST = hashlib.sha256(b'storefront-bytes').hexdigest()
SENTINEL_ORIGIN = 'https://sentinel-origin.test/item'
SENTINEL_DOWNLOAD = 'https://sentinel-origin.test/item.bin'
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
BUYER_HEADER = 'X-Buyer-Id'
BUYER_ID = 'refusal-buyer'
ENTITLED_BUYER = 'refusal-entitled-buyer'
GRANT_LIFETIME_SECONDS = 900
RETURN_URL = 'https://shop.example/return'
_GRANT_SECRET = SecretStr('storefront-unit-grant-secret')
_OPERATOR_KEY = SecretStr('storefront-unit-operator-key')
_UNIT_AMOUNT = Decimal('9.99')
_CURRENCY = 'BYN'


class StorefrontHarness:
    """The API over an in-memory store, plus a good whose origin is a sentinel."""

    def __init__(self, tmp_path: Path) -> None:
        self.store = InMemoryStore()
        self.cache = AssetCache(root=tmp_path, max_bytes=1024)
        self.http = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(404))
        )
        self.grants = DeliveryGrantService(
            secret=_GRANT_SECRET, lifetime_seconds=GRANT_LIFETIME_SECONDS
        )
        delivery = DeliveryService(
            entitlements=self.store,
            entries=self.store,
            cache=self.cache,
            http=self.http,
        )
        stripe = StripeProvider(
            secret_key=SecretStr('sk_test_storefront'),
            webhook_secret=SecretStr('whsec_storefront'),
            http=self.http,
        )
        bepaid = BePaidProvider(
            shop_id='storefront-shop',
            secret_key=SecretStr('bepaid_storefront'),
            public_key_pem=BEPAID_PUBLIC_KEY_PEM,
            http=self.http,
            notification_url='https://shop.example/webhooks/bepaid',
        )
        checkout = CheckoutService(
            entries=self.store,
            disclosures=self.store,
            orders=self.store,
            entitlements=self.store,
            providers={'stripe': stripe, 'bepaid': bepaid},
        )
        self.app: FastAPI = ApiApplication(
            'test',
            grants=self.grants,
            delivery=delivery,
            entitlements=self.store,
            clock=lambda: NOW,
            checkout=checkout,
            disclosures=self.store,
            stripe=stripe,
            bepaid=bepaid,
            orders=self.store,
            operator_refund_key=_OPERATOR_KEY,
            catalogue=build_catalogue(self.store, _UNIT_AMOUNT, _CURRENCY),
            preview=build_preview(self.store, self.cache, self.http),
            storefront_domain='shop.example',
        ).build()
        self.client = TestClient(self.app)

    async def stock_a_good(self) -> None:
        await self.store.upsert_many(
            (
                build_candidate(candidate_id=CANDIDATE_ID).model_copy(
                    update={
                        'landing_url': SENTINEL_ORIGIN,
                        'download_url': SENTINEL_DOWNLOAD,
                    }
                ),
            )
        )
        await self.store.save_entry(
            CatalogueEntry(
                candidate_id=CANDIDATE_ID,
                source_id='openverse',
                saleor_product_id='product-1',
                saleor_variant_id='variant-1',
                category_id=None,
                license_id='CC-BY-4.0',
                obligations=(),
                listing=StorefrontListing.PAID_OK,
                state=CatalogueEntryState.PUBLISHED,
                withdrawal_reason=None,
                published_at=NOW,
                content_digest=DIGEST,
                origin_url=SENTINEL_ORIGIN,
            )
        )

    def parameterless_paths(self) -> list[str]:
        return [
            route.path
            for route in self.app.routes
            if isinstance(route, APIRoute) and '{' not in route.path
        ]


def test_no_registered_route_serves_html(tmp_path: Path) -> None:
    """The regression guard: the leak was an HTML page at the root."""
    harness = StorefrontHarness(tmp_path)

    html_routes: list[str] = []
    for route in harness.app.routes:
        if not isinstance(route, APIRoute):
            continue
        declared = route.response_class
        resolved = declared.value if isinstance(declared, DefaultPlaceholder) else declared
        if issubclass(resolved, HTMLResponse) or resolved.media_type == 'text/html':
            html_routes.append(route.path)

    assert html_routes == []


async def test_the_root_is_a_json_descriptor_that_names_no_good(tmp_path: Path) -> None:
    harness = StorefrontHarness(tmp_path)
    await harness.stock_a_good()

    response = harness.client.get('/')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/json')
    assert response.json() == {'service': ApiApplication.SERVICE_NAME, 'status': 'ok'}
    assert 'Sample good' not in response.text
    assert 'http' not in response.text
    assert SENTINEL_ORIGIN not in response.text
    assert SENTINEL_DOWNLOAD not in response.text


async def test_no_parameterless_route_discloses_an_origin(tmp_path: Path) -> None:
    harness = StorefrontHarness(tmp_path)
    await harness.stock_a_good()

    # Path-parameter routes are skipped: /catalogue/categories/{slug},
    # /catalogue/goods/{candidate_id}, /catalogue/goods/{candidate_id}/preview,
    # /account/goods/{candidate_id}/grant, /downloads/{token} and
    # /ops/orders/{order_id}/refund all need an id this test has no reason to
    # invent. The catalogue card routes that take one are pinned by
    # test_catalogue_browse.py, which stocks a real entry and asserts its body
    # names no origin, digest or storage path.
    paths = harness.parameterless_paths()
    assert paths

    # The store must actually hold the good, or the sweep proves nothing: a
    # route that returns no goods cannot leak one.
    listed = harness.client.get('/catalogue/goods').json()
    assert [item['candidate_id'] for item in listed['items']] == [CANDIDATE_ID]

    for path in paths:
        response = harness.client.get(path)
        assert SENTINEL_ORIGIN not in response.text, path
        assert SENTINEL_DOWNLOAD not in response.text, path


async def test_no_refusal_route_discloses_an_origin(tmp_path: Path) -> None:
    """An origin must not re-enter a body through a refusal message.

    The sweep above skips every route that takes a path parameter, and those are
    the ones that answer with a refusal: a grant for a good the buyer does not
    own, a download behind an unknown or expired token, a download whose origin
    refuses, and a checkout the service turns down. Each detail is ``str(error)``
    for ``GrantRefusedError``, ``DeliveryRefusedError`` or
    ``CheckoutRefusedError``, so a future message that quoted the origin - or a
    domain error that wrapped an httpx error carrying it - would print straight
    into the body. ``delivery.py`` forbids that in a comment; this test is the
    guard a comment cannot be.

    The check is for a lowercase ``http`` on purpose: the origin refuses with
    "the origin returned HTTP 404", a status and not a scheme, and that is the
    only reason the guard may be case-sensitive.
    """
    harness = StorefrontHarness(tmp_path)
    await harness.stock_a_good()
    await harness.store.save_entitlement(
        Entitlement(
            buyer_id=ENTITLED_BUYER,
            candidate_id=CANDIDATE_ID,
            order_id='order-refusal',
            granted_at=NOW,
            state=EntitlementState.ACTIVE,
            revoked_at=None,
            revocation_reason=None,
        )
    )
    expired_token, _ = harness.grants.issue(
        BUYER_ID, CANDIDATE_ID, NOW - timedelta(seconds=GRANT_LIFETIME_SECONDS + 100)
    )
    live_token, _ = harness.grants.issue(ENTITLED_BUYER, CANDIDATE_ID, NOW)

    refusals = {
        'a grant for a good the buyer does not own': (
            harness.client.post(
                f'/account/goods/{CANDIDATE_ID}/grant',
                headers={BUYER_HEADER: BUYER_ID},
            ),
            403,
        ),
        'a download behind an unknown token': (
            harness.client.get(
                '/downloads/not-a-real-grant',
                headers={BUYER_HEADER: BUYER_ID},
            ),
            403,
        ),
        'a download behind an expired token': (
            harness.client.get(
                f'/downloads/{expired_token}',
                headers={BUYER_HEADER: BUYER_ID},
            ),
            403,
        ),
        'a download whose origin refuses': (
            harness.client.get(
                f'/downloads/{live_token}',
                headers={BUYER_HEADER: ENTITLED_BUYER},
            ),
            403,
        ),
        'a checkout start the service turns down': (
            harness.client.post(
                '/checkout/start',
                headers={BUYER_HEADER: BUYER_ID},
                json={
                    'provider_id': 'stripe',
                    'return_url': RETURN_URL,
                    'currency': _CURRENCY,
                    'lines': [
                        {
                            'candidate_id': CANDIDATE_ID,
                            'unit_amount': '9.99',
                            'quantity': 1,
                        }
                    ],
                },
            ),
            403,
        ),
    }

    for label, (response, status) in refusals.items():
        # The documented status and a real refusal detail, so a route that
        # silently started answering "200 {}" cannot pass by returning nothing.
        assert response.status_code == status, label
        assert response.content != b'', label
        assert 'detail' in response.json(), label
        assert response.json()['detail'] != '', label
        assert SENTINEL_ORIGIN not in response.text, label
        assert SENTINEL_DOWNLOAD not in response.text, label
        assert 'http' not in response.text, label


def test_health_reports_the_environment(tmp_path: Path) -> None:
    harness = StorefrontHarness(tmp_path)

    response = harness.client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'environment': 'test'}
