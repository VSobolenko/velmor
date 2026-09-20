from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from pydantic import SecretStr

from packages.services.src.domain.order import Order, OrderLine, OrderState
from packages.services.src.payments.bepaid_provider import BePaidProvider
from packages.services.src.payments.errors import (
    PaymentNotificationError,
    PaymentProviderError,
)

SHOP_ID = 'bepaid-shop-42'
SECRET_KEY = 'bepaid_secret_key_unit_test_not_real'
CHECKOUT_TOKEN = '3241e439f8c87d941d92621a4bdc030d4c9a69c67f3b0cfe12de4a13cc34aa51'
REDIRECT_URL = (
    f'https://checkout.bepaid.by/v2/checkout?token={CHECKOUT_TOKEN}'
)
TRANSACTION_UID = 'dd6ee60c-d30a-4348-b84c-86a4ef1a137d'
ORDER_ID = 'order-42'
RETURN_URL = 'https://shop.example/return'
NOTIFICATION_URL = 'https://shop.example/webhooks/bepaid'
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def _generate_rsa_keypair() -> tuple[str, rsa.RSAPrivateKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode('utf-8')
    )
    return public_pem, private_key


PUBLIC_KEY_PEM, PRIVATE_KEY = _generate_rsa_keypair()


def sign_payload(payload: bytes, private_key: rsa.RSAPrivateKey = PRIVATE_KEY) -> str:
    signature = private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode('ascii')


def basic_authorization(shop_id: str = SHOP_ID, secret: str = SECRET_KEY) -> str:
    token = base64.b64encode(f'{shop_id}:{secret}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def build_order(
    *,
    currency: str = 'BYN',
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


def transaction_payload(
    *,
    status: str = 'successful',
    amount: int = 1050,
    currency: str = 'BYN',
    tracking_id: str = ORDER_ID,
    uid: str = TRANSACTION_UID,
) -> bytes:
    body = {
        'transaction': {
            'uid': uid,
            'status': status,
            'amount': amount,
            'currency': currency,
            'tracking_id': tracking_id,
            'type': 'payment',
            'test': True,
        }
    }
    return json.dumps(body, separators=(',', ':')).encode('utf-8')


def build_provider(http: httpx.AsyncClient) -> BePaidProvider:
    return BePaidProvider(
        shop_id=SHOP_ID,
        secret_key=SecretStr(SECRET_KEY),
        public_key_pem=PUBLIC_KEY_PEM,
        http=http,
        notification_url=NOTIFICATION_URL,
    )


class TestStartPayment:
    async def test_creates_checkout_with_basic_auth_minor_units_and_test(
        self,
    ) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    'checkout': {
                        'token': CHECKOUT_TOKEN,
                        'redirect_url': REDIRECT_URL,
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            start = await build_provider(http).start_payment(build_order(), RETURN_URL)

        assert start.redirect_url == REDIRECT_URL
        assert start.provider_reference == CHECKOUT_TOKEN
        assert len(captured) == 1
        request = captured[0]
        assert request.method == 'POST'
        assert str(request.url) == 'https://checkout.bepaid.by/ctp/api/checkouts'
        assert request.headers['Authorization'] == basic_authorization()
        assert request.headers['Content-Type'] == 'application/json'
        assert request.headers['Accept'] == 'application/json'
        assert request.headers['X-API-Version'] == '2'
        body = json.loads(request.content.decode('utf-8'))
        checkout = body['checkout']
        assert checkout['transaction_type'] == 'payment'
        assert checkout['test'] is True
        assert checkout['order']['amount'] == 1050
        assert checkout['order']['currency'] == 'BYN'
        assert checkout['order']['tracking_id'] == ORDER_ID
        assert checkout['settings']['notification_url'] == NOTIFICATION_URL
        assert 'payment_method' not in checkout

    async def test_http_500_and_transport_error_raise_provider_error(self) -> None:
        def fail_500(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={'message': 'boom'})

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
    def test_valid_content_signature_successful_payment(self) -> None:
        payload = transaction_payload()
        header = sign_payload(payload)
        provider = BePaidProvider(
            shop_id=SHOP_ID,
            secret_key=SecretStr(SECRET_KEY),
            public_key_pem=PUBLIC_KEY_PEM,
            http=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200))
            ),
            notification_url=NOTIFICATION_URL,
        )

        confirmation = provider.parse_notification(payload, header, None)

        assert confirmation.succeeded is True
        assert confirmation.order_id == ORDER_ID
        assert confirmation.provider_reference == TRANSACTION_UID
        assert confirmation.amount == Decimal('10.50')
        assert confirmation.currency == 'BYN'

    def test_valid_signature_expired_yields_non_succeeded(self) -> None:
        payload = transaction_payload(status='expired')
        header = sign_payload(payload)
        provider = BePaidProvider(
            shop_id=SHOP_ID,
            secret_key=SecretStr(SECRET_KEY),
            public_key_pem=PUBLIC_KEY_PEM,
            http=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200))
            ),
            notification_url=NOTIFICATION_URL,
        )

        confirmation = provider.parse_notification(payload, header, None)

        assert confirmation.succeeded is False
        assert confirmation.order_id == ORDER_ID
        assert confirmation.provider_reference == TRANSACTION_UID

    def test_forged_signature_is_refused(self) -> None:
        payload = transaction_payload()
        other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        header = sign_payload(payload, other_private)
        provider = BePaidProvider(
            shop_id=SHOP_ID,
            secret_key=SecretStr(SECRET_KEY),
            public_key_pem=PUBLIC_KEY_PEM,
            http=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200))
            ),
            notification_url=NOTIFICATION_URL,
        )

        with pytest.raises(PaymentNotificationError):
            provider.parse_notification(payload, header, None)

    def test_basic_auth_only_successful_body(self) -> None:
        payload = transaction_payload()
        provider = BePaidProvider(
            shop_id=SHOP_ID,
            secret_key=SecretStr(SECRET_KEY),
            public_key_pem=PUBLIC_KEY_PEM,
            http=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200))
            ),
            notification_url=NOTIFICATION_URL,
        )

        confirmation = provider.parse_notification(
            payload, None, basic_authorization()
        )

        assert confirmation.succeeded is True
        assert confirmation.order_id == ORDER_ID
        assert confirmation.provider_reference == TRANSACTION_UID

    def test_bad_basic_auth_is_refused(self) -> None:
        payload = transaction_payload()
        provider = BePaidProvider(
            shop_id=SHOP_ID,
            secret_key=SecretStr(SECRET_KEY),
            public_key_pem=PUBLIC_KEY_PEM,
            http=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200))
            ),
            notification_url=NOTIFICATION_URL,
        )

        with pytest.raises(PaymentNotificationError):
            provider.parse_notification(
                payload, None, basic_authorization(secret='wrong-secret')
            )

    def test_parse_is_deterministic_for_the_same_payload(self) -> None:
        payload = transaction_payload()
        header = sign_payload(payload)
        provider = BePaidProvider(
            shop_id=SHOP_ID,
            secret_key=SecretStr(SECRET_KEY),
            public_key_pem=PUBLIC_KEY_PEM,
            http=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200))
            ),
            notification_url=NOTIFICATION_URL,
        )

        first = provider.parse_notification(payload, header, None)
        second = provider.parse_notification(payload, header, None)

        assert first == second
        assert first.model_dump() == second.model_dump()


class TestSecretHandling:
    def test_secret_and_pem_are_not_leaked_in_repr_or_attrs(self) -> None:
        provider = BePaidProvider(
            shop_id=SHOP_ID,
            secret_key=SecretStr(SECRET_KEY),
            public_key_pem=PUBLIC_KEY_PEM,
            http=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200))
            ),
            notification_url=NOTIFICATION_URL,
        )

        assert SECRET_KEY not in repr(provider)
        assert SECRET_KEY not in str(provider)
        assert 'BEGIN PUBLIC KEY' not in repr(provider)
        assert 'BEGIN PUBLIC KEY' not in str(provider)
        for name, value in vars(provider).items():
            assert SECRET_KEY not in repr(value), name
            assert SECRET_KEY not in str(value), name
            assert 'BEGIN PUBLIC KEY' not in repr(value), name
            assert 'BEGIN PUBLIC KEY' not in str(value), name
