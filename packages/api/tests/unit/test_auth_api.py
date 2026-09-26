"""The HTTP surface of buyer accounts.

Every route here is exercised through the same app the rest of the API tests
build, so a cookie set by ``/auth/register`` is the only thing that authenticates
a request: no test passes a buyer identity as a header, because the surface no
longer reads one.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from packages.api.src.app import ApiApplication
from packages.api.tests.unit.storefront_services import (
    TEST_FAILED_ATTEMPT_LIMIT,
    TEST_PASSWORD_MIN_LENGTH,
    TEST_SESSION_COOKIE_NAME,
    TEST_SESSION_LIFETIME_SECONDS,
)
from packages.api.tests.unit.test_commerce_api import (
    BUYER_EMAIL,
    BUYER_PASSWORD,
    NOW,
    CommerceHarness,
    build_disclosure,
    build_entry,
)
from packages.services.src.auth.service import AccountService
from packages.services.src.domain.license import StorefrontListing

NEW_PASSWORD = 'a differently worded buyer password'
UNKNOWN_EMAIL = 'nobody@example.test'
WRONG_PASSWORD = 'the wrong password value'
REGISTRATION = {
    'email': 'new-buyer@example.test',
    'password': 'a brand new buyer password',
    'display_name': 'New Buyer',
}


def sign_in(harness: CommerceHarness, email: str = BUYER_EMAIL) -> TestClient:
    """A fresh client that has signed in and holds the session cookie."""
    client = harness.new_client()
    response = client.post(
        '/auth/session', json={'email': email, 'password': BUYER_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


class TestRegistration:
    def test_a_new_address_creates_an_account_and_sets_the_cookie(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)

        response = harness.new_client().post('/auth/register', json=REGISTRATION)

        assert response.status_code == 201
        body = response.json()
        assert body['email'] == REGISTRATION['email']
        assert body['display_name'] == REGISTRATION['display_name']
        assert body['id']
        assert set(body) == {'id', 'email', 'display_name'}
        assert REGISTRATION['password'] not in response.text

        cookie = response.headers['set-cookie'].lower()
        assert TEST_SESSION_COOKIE_NAME in cookie
        assert 'httponly' in cookie
        assert 'secure' in cookie
        assert 'samesite=lax' in cookie
        assert 'path=/' in cookie
        assert 'max-age=' in cookie

    def test_the_registered_buyer_is_already_signed_in(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        client = harness.new_client()
        created = client.post('/auth/register', json=REGISTRATION).json()

        response = client.get('/auth/me')

        assert response.status_code == 200
        assert response.json()['id'] == created['id']
        assert response.json()['email'] == REGISTRATION['email']
        assert 'password' not in response.text
        assert 'password_hash' not in response.text
        assert 'password_salt' not in response.text

    def test_a_duplicate_address_is_refused_and_names_only_the_address(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        taken = {**REGISTRATION, 'email': BUYER_EMAIL.upper()}

        response = harness.new_client().post('/auth/register', json=taken)

        assert response.status_code == 400
        assert response.json()['reason'] == AccountService.EMAIL_UNAVAILABLE
        assert BUYER_PASSWORD not in response.text

    def test_a_password_below_the_minimum_names_the_length(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        short = {**REGISTRATION, 'password': 'short'}

        response = harness.new_client().post('/auth/register', json=short)

        assert response.status_code == 400
        body = response.json()
        assert body['reason'] == AccountService.PASSWORD_TOO_SHORT
        assert body['minimum_length'] == TEST_PASSWORD_MIN_LENGTH

    def test_an_empty_address_is_refused(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        empty = {**REGISTRATION, 'email': '   '}

        response = harness.new_client().post('/auth/register', json=empty)

        assert response.status_code == 400
        assert response.json()['reason'] == AccountService.EMAIL_REQUIRED


class TestSignInAndOut:
    def test_correct_credentials_sign_the_buyer_in(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        client = harness.new_client()

        response = client.post(
            '/auth/session', json={'email': BUYER_EMAIL, 'password': BUYER_PASSWORD}
        )

        assert response.status_code == 200
        assert response.json()['email'] == BUYER_EMAIL
        assert client.get('/auth/me').status_code == 200

    def test_a_wrong_password_and_an_unknown_address_are_refused_identically(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        client = harness.new_client()

        wrong = client.post(
            '/auth/session', json={'email': BUYER_EMAIL, 'password': WRONG_PASSWORD}
        )
        unknown = client.post(
            '/auth/session', json={'email': UNKNOWN_EMAIL, 'password': WRONG_PASSWORD}
        )

        assert wrong.status_code == 401
        assert unknown.status_code == 401
        assert wrong.json() == unknown.json()
        assert wrong.json()['reason'] == AccountService.INVALID_CREDENTIALS

    def test_signing_out_revokes_the_session_and_clears_the_cookie(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        client = sign_in(harness)
        assert client.get('/auth/me').status_code == 200

        response = client.delete('/auth/session')

        assert response.status_code == 200
        assert response.json() == {'ok': True}
        assert client.get('/auth/me').status_code == 401


class TestSessionResolution:
    def test_a_request_with_no_session_is_refused_as_unauthenticated(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)

        response = harness.new_client().get('/auth/me')

        assert response.status_code == 401
        assert response.json() == {
            'detail': ApiApplication.UNAUTHENTICATED_DETAIL,
            'reason': ApiApplication.UNAUTHENTICATED,
        }

    def test_the_removed_buyer_header_grants_nothing(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)

        response = harness.new_client().get(
            '/account/entitlements', headers={'X-Buyer-Id': harness.buyer_id}
        )

        assert response.status_code == 401
        assert response.json()['reason'] == ApiApplication.UNAUTHENTICATED

    def test_an_expired_session_is_refused(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        client = sign_in(harness)
        harness.clock.instant = NOW + timedelta(seconds=TEST_SESSION_LIFETIME_SECONDS)

        response = client.get('/auth/me')

        assert response.status_code == 401
        assert response.json()['reason'] == ApiApplication.UNAUTHENTICATED

    def test_a_revoked_session_is_refused_immediately(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        client = sign_in(harness)
        stole = client.cookies[TEST_SESSION_COOKIE_NAME]
        client.delete('/auth/session')

        impostor = harness.new_client()
        impostor.cookies.set(TEST_SESSION_COOKIE_NAME, stole)

        response = impostor.get('/auth/me')

        assert response.status_code == 401
        assert response.json()['reason'] == ApiApplication.UNAUTHENTICATED


class TestProtectedRoutes:
    def test_every_owner_route_refuses_without_a_session(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        client = harness.new_client()
        calls = (
            ('get', '/account/entitlements'),
            ('get', '/account/orders'),
            ('get', '/account/orders/order-missing'),
            ('post', '/account/goods/openverse:1/grant'),
            ('get', '/downloads/not-a-real-grant'),
        )

        for method, path in calls:
            response = getattr(client, method)(path)
            assert response.status_code == 401, path
            assert response.json()['reason'] == ApiApplication.UNAUTHENTICATED, path


class TestCheckoutWithoutASession:
    async def test_no_order_is_created_and_no_payment_is_started(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry())

        response = harness.new_client().post(
            '/checkout/start', json=harness.start_body()
        )

        assert response.status_code == 401
        assert response.json()['reason'] == ApiApplication.UNAUTHENTICATED
        assert harness.stripe_calls == []

    async def test_a_signed_in_buyer_still_cannot_start_a_refused_checkout(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        await harness.store.save_disclosure(build_disclosure())
        await harness.store.save_entry(build_entry(listing=StorefrontListing.FREE_ONLY))

        response = harness.client.post('/checkout/start', json=harness.start_body())

        assert response.status_code == 403
        assert harness.stripe_calls == []


class TestChangePassword:
    def test_a_wrong_current_password_is_refused_and_the_old_one_still_works(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)
        client = sign_in(harness)

        response = client.post(
            '/auth/password',
            json={'current_password': WRONG_PASSWORD, 'new_password': NEW_PASSWORD},
        )

        assert response.status_code == 400
        assert response.json()['reason'] == AccountService.CURRENT_PASSWORD_INCORRECT
        assert harness.new_client().post(
            '/auth/session', json={'email': BUYER_EMAIL, 'password': BUYER_PASSWORD}
        ).status_code == 200

    def test_a_short_new_password_is_refused(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        client = sign_in(harness)

        response = client.post(
            '/auth/password',
            json={'current_password': BUYER_PASSWORD, 'new_password': 'short'},
        )

        assert response.status_code == 400
        body = response.json()
        assert body['reason'] == AccountService.PASSWORD_TOO_SHORT
        assert body['minimum_length'] == TEST_PASSWORD_MIN_LENGTH

    def test_changing_the_password_closes_the_other_session(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        acting = sign_in(harness)
        other = sign_in(harness)

        response = acting.post(
            '/auth/password',
            json={'current_password': BUYER_PASSWORD, 'new_password': NEW_PASSWORD},
        )

        assert response.status_code == 200
        assert acting.get('/auth/me').status_code == 200
        assert other.get('/auth/me').status_code == 401

    def test_a_request_without_a_session_cannot_change_a_password(
        self, tmp_path: Path
    ) -> None:
        harness = CommerceHarness(tmp_path)

        response = harness.new_client().post(
            '/auth/password',
            json={'current_password': BUYER_PASSWORD, 'new_password': NEW_PASSWORD},
        )

        assert response.status_code == 401
        assert response.json()['reason'] == ApiApplication.UNAUTHENTICATED


class TestRateLimit:
    def test_repeated_failures_are_refused_as_rate_limited(self, tmp_path: Path) -> None:
        harness = CommerceHarness(tmp_path)
        client = harness.new_client()
        for _attempt in range(TEST_FAILED_ATTEMPT_LIMIT):
            refused = client.post(
                '/auth/session', json={'email': BUYER_EMAIL, 'password': WRONG_PASSWORD}
            )
            assert refused.status_code == 401

        throttled = client.post(
            '/auth/session', json={'email': BUYER_EMAIL, 'password': BUYER_PASSWORD}
        )

        assert throttled.status_code == 429
        assert throttled.json()['reason'] == AccountService.RATE_LIMITED
