from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import SecretStr

from packages.services.src.domain.order import Order, OrderLine, OrderState
from packages.services.src.payments.errors import PaymentNotificationError
from packages.services.src.payments.stub_provider import StubPaymentProvider

WEBHOOK_SECRET = 'stub-unit-webhook-secret'
ORDER_ID = 'order-stub-42'
RETURN_URL = 'https://shop.example/return'
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def sign_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()


def build_order(
    *,
    currency: str = 'USD',
    unit_amount: Decimal = Decimal('9.99'),
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


def success_payload(
    *,
    order_id: str = ORDER_ID,
    amount: str = '9.99',
    currency: str = 'USD',
    succeeded: bool = True,
    provider_reference: str | None = None,
) -> bytes:
    body = {
        'order_id': order_id,
        'amount': amount,
        'currency': currency,
        'succeeded': succeeded,
        'provider_reference': provider_reference or f'stub-{order_id}',
    }
    return json.dumps(body, separators=(',', ':')).encode('utf-8')


def build_provider() -> StubPaymentProvider:
    return StubPaymentProvider(webhook_secret=SecretStr(WEBHOOK_SECRET))


class TestStubStartPayment:
    async def test_redirect_is_return_url_with_order_id(self) -> None:
        start = await build_provider().start_payment(build_order(), RETURN_URL)

        assert start.provider_reference == f'stub-{ORDER_ID}'
        assert start.redirect_url == f'{RETURN_URL}?order_id={ORDER_ID}'

    async def test_provider_id_is_stub(self) -> None:
        assert build_provider().provider_id == 'stub'


class TestStubParseNotification:
    def test_valid_signature_yields_confirmation(self) -> None:
        payload = success_payload()
        confirmation = build_provider().parse_notification(
            payload, sign_payload(payload)
        )

        assert confirmation.order_id == ORDER_ID
        assert confirmation.amount == Decimal('9.99')
        assert confirmation.currency == 'USD'
        assert confirmation.succeeded is True
        assert confirmation.provider_reference == f'stub-{ORDER_ID}'

    def test_missing_signature_raises_notification_error(self) -> None:
        with pytest.raises(PaymentNotificationError, match='missing'):
            build_provider().parse_notification(success_payload(), '')

    def test_invalid_signature_raises_notification_error(self) -> None:
        with pytest.raises(PaymentNotificationError, match='verification failed'):
            build_provider().parse_notification(success_payload(), 'deadbeef')

    def test_wrong_secret_raises_notification_error(self) -> None:
        payload = success_payload()
        with pytest.raises(PaymentNotificationError, match='verification failed'):
            build_provider().parse_notification(
                payload, sign_payload(payload, secret='other-secret')
            )
