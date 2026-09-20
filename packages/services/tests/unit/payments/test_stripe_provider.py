from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from packages.services.src.domain.order import Order, OrderLine, OrderState
from packages.services.src.payments.errors import (
    PaymentNotificationError,
    PaymentProviderError,
)
from packages.services.src.payments.stripe_provider import StripeProvider

SECRET_KEY = 'sk_test_unit_stripe_secret_key_not_real'
WEBHOOK_SECRET = 'whsec_unit_test_webhook_signing_secret'
SESSION_ID = 'cs_test_unit_session_abc'
SESSION_URL = 'https://checkout.stripe.com/c/pay/cs_test_unit_session_abc'
ORDER_ID = 'order-42'
RETURN_URL = 'https://shop.example/return'
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def sign_payload(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Build a Stripe-Signature header with the documented v1 HMAC scheme."""
    ts = int(time.time()) if timestamp is None else timestamp
    signed_payload = f'{ts}.{payload.decode("utf-8")}'
    digest = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return f't={ts},v1={digest}'


def build_order(
    *,
    currency: str = 'USD',
    unit_amount: Decimal = Decimal('10.50'),
    quantity: int = 1,
) -> Order:
    line = OrderLine(
        candidate_id='openverse:1',
        unit_amount=unit_amount,
        quantity=quantity,
    )
    return Order(
        order_id=ORDER_ID,
        buyer_id='buyer-1',
        state=OrderState.PENDING,
        currency=currency,
        lines=(line,),
        total=unit_amount * quantity,
        provider_id=None,
        provider_reference=None,
        created_at=NOW,
        paid_at=None,
    )


def completed_event_payload(
    *,
    amount_total: int = 1050,
    currency: str = 'usd',
    order_id: str = ORDER_ID,
    session_id: str = SESSION_ID,
) -> bytes:
    event = {
        'id': 'evt_test_1',
        'object': 'event',
        'type': 'checkout.session.completed',
        'data': {
            'object': {
                'id': session_id,
                'object': 'checkout.session',
                'client_reference_id': order_id,
                'metadata': {'order_id': order_id},
                'amount_total': amount_total,
                'currency': currency,
                'payment_status': 'paid',
                'status': 'complete',
            }
        },
    }
    return json.dumps(event, separators=(',', ':')).encode('utf-8')


def expired_event_payload() -> bytes:
    event = {
        'id': 'evt_test_expired',
        'object': 'event',
        'type': 'checkout.session.expired',
        'data': {
            'object': {
                'id': SESSION_ID,
                'object': 'checkout.session',
                'client_reference_id': ORDER_ID,
                'metadata': {'order_id': ORDER_ID},
                'amount_total': 1050,
                'currency': 'usd',
                'payment_status': 'unpaid',
                'status': 'expired',
            }
        },
    }
    return json.dumps(event, separators=(',', ':')).encode('utf-8')


def build_provider(http: httpx.AsyncClient) -> StripeProvider:
    return StripeProvider(
        secret_key=SecretStr(SECRET_KEY),
        webhook_secret=SecretStr(WEBHOOK_SECRET),
        http=http,
    )


class TestStartPayment:
    async def test_creates_checkout_session_with_cents_and_bearer(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    'id': SESSION_ID,
                    'object': 'checkout.session',
                    'url': SESSION_URL,
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            start = await build_provider(http).start_payment(build_order(), RETURN_URL)

        assert start.redirect_url == SESSION_URL
        assert start.provider_reference == SESSION_ID
        assert len(captured) == 1
        request = captured[0]
        assert request.method == 'POST'
        assert str(request.url) == 'https://api.stripe.com/v1/checkout/sessions'
        assert request.headers['Authorization'] == f'Bearer {SECRET_KEY}'
        form = parse_qs(request.content.decode('utf-8'))
        assert form['mode'] == ['payment']
        assert form['client_reference_id'] == [ORDER_ID]
        assert form['metadata[order_id]'] == [ORDER_ID]
        assert form['line_items[0][price_data][unit_amount]'] == ['1050']
        assert form['line_items[0][price_data][currency]'] == ['usd']
        assert form['line_items[0][quantity]'] == ['1']
        assert 'checkout=success' in form['success_url'][0]
        assert 'checkout=cancel' in form['cancel_url'][0]
        assert form['success_url'][0].startswith(RETURN_URL)
        assert form['cancel_url'][0].startswith(RETURN_URL)

    async def test_stripe_http_500_and_transport_error_raise_provider_error(self) -> None:
        def fail_500(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={'error': {'message': 'boom'}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_500)) as http:
            with pytest.raises(PaymentProviderError, match='500'):
                await build_provider(http).start_payment(build_order(), RETURN_URL)

        def fail_transport(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError('refused', request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_transport)) as http:
            with pytest.raises(PaymentProviderError) as raised:
                await build_provider(http).start_payment(build_order(), RETURN_URL)

        assert raised.value.__cause__ is not None
        assert isinstance(raised.value.__cause__, httpx.RequestError)


class TestParseNotification:
    def test_valid_completed_event_returns_confirmation(self) -> None:
        payload = completed_event_payload()
        header = sign_payload(payload, WEBHOOK_SECRET)
        async_http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))

        confirmation = StripeProvider(
            secret_key=SecretStr(SECRET_KEY),
            webhook_secret=SecretStr(WEBHOOK_SECRET),
            http=async_http,
        ).parse_notification(payload, header)

        assert confirmation.succeeded is True
        assert confirmation.order_id == ORDER_ID
        assert confirmation.provider_reference == SESSION_ID
        assert confirmation.amount == Decimal('10.50')
        assert confirmation.currency == 'USD'

    def test_bad_signature_refuses_without_confirmation(self) -> None:
        payload = completed_event_payload()
        header = sign_payload(payload, 'whsec_wrong_secret')
        provider = StripeProvider(
            secret_key=SecretStr(SECRET_KEY),
            webhook_secret=SecretStr(WEBHOOK_SECRET),
            http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
        )

        with pytest.raises(PaymentNotificationError):
            provider.parse_notification(payload, header)

    def test_missing_signature_header_is_refused(self) -> None:
        payload = completed_event_payload()
        provider = StripeProvider(
            secret_key=SecretStr(SECRET_KEY),
            webhook_secret=SecretStr(WEBHOOK_SECRET),
            http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
        )

        with pytest.raises(PaymentNotificationError):
            provider.parse_notification(payload, '')

    def test_unknown_event_type_is_refused(self) -> None:
        event = {
            'id': 'evt_other',
            'object': 'event',
            'type': 'customer.created',
            'data': {'object': {'id': 'cus_1'}},
        }
        payload = json.dumps(event, separators=(',', ':')).encode('utf-8')
        header = sign_payload(payload, WEBHOOK_SECRET)
        provider = StripeProvider(
            secret_key=SecretStr(SECRET_KEY),
            webhook_secret=SecretStr(WEBHOOK_SECRET),
            http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
        )

        with pytest.raises(PaymentNotificationError, match='customer.created'):
            provider.parse_notification(payload, header)

    def test_parse_is_deterministic_for_the_same_payload(self) -> None:
        payload = completed_event_payload()
        header = sign_payload(payload, WEBHOOK_SECRET)
        provider = StripeProvider(
            secret_key=SecretStr(SECRET_KEY),
            webhook_secret=SecretStr(WEBHOOK_SECRET),
            http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
        )

        first = provider.parse_notification(payload, header)
        second = provider.parse_notification(payload, header)

        assert first == second
        assert first.model_dump() == second.model_dump()

    def test_expired_session_yields_non_succeeded_confirmation(self) -> None:
        payload = expired_event_payload()
        header = sign_payload(payload, WEBHOOK_SECRET)
        provider = StripeProvider(
            secret_key=SecretStr(SECRET_KEY),
            webhook_secret=SecretStr(WEBHOOK_SECRET),
            http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
        )

        confirmation = provider.parse_notification(payload, header)

        assert confirmation.succeeded is False
        assert confirmation.order_id == ORDER_ID
        assert confirmation.provider_reference == SESSION_ID


class TestSecretHandling:
    def test_secrets_are_not_reachable_from_repr_or_attributes(self) -> None:
        provider = StripeProvider(
            secret_key=SecretStr(SECRET_KEY),
            webhook_secret=SecretStr(WEBHOOK_SECRET),
            http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
        )

        assert SECRET_KEY not in repr(provider)
        assert WEBHOOK_SECRET not in repr(provider)
        assert SECRET_KEY not in str(provider)
        assert WEBHOOK_SECRET not in str(provider)
        for name, value in vars(provider).items():
            assert SECRET_KEY not in repr(value), name
            assert WEBHOOK_SECRET not in repr(value), name
            assert SECRET_KEY not in str(value), name
            assert WEBHOOK_SECRET not in str(value), name
