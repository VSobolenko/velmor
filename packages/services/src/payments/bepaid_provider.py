"""bePaid hosted-checkout payment provider (test mode).

Cards and ERIP are both available because the checkout request does not
restrict ``payment_method`` types; the hosted page shows every method enabled
for the shop. Live bePaid is not claimed here - callers supply test credentials
and tests use MockTransport plus a local RSA keypair.
"""

from __future__ import annotations

import base64
import hmac
import json
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from pydantic import SecretStr

from packages.services.src.domain.order import Order
from packages.services.src.payments.errors import (
    PaymentNotificationError,
    PaymentProviderError,
)
from packages.services.src.payments.protocol import PaymentConfirmation, PaymentStart


class BePaidProvider:
    """PaymentProvider for bePaid hosted checkout via httpx.

    Notification authenticity follows the published bePaid webhook contract
    (https://docs.bepaid.by/en/using_api/webhooks/): RSA-SHA256 over the raw
    body in ``Content-Signature``, or HTTP Basic with shop id and secret when
    the signature header is absent.
    """

    PROVIDER_ID = 'bepaid'
    CHECKOUTS_URL = 'https://checkout.bepaid.by/ctp/api/checkouts'
    AUTH_FAILURE_STATUSES = frozenset({401, 403})
    HTTP_ERROR_FLOOR = 400
    SUPPORTED_CURRENCIES = frozenset({'BYN', 'USD', 'EUR'})
    MINOR_UNITS_PER_MAJOR = Decimal(100)
    SUCCESS_STATUSES = frozenset({'successful', 'paid'})
    FAILURE_STATUSES = frozenset({'failed', 'declined', 'expired'})
    BASIC_PREFIX = 'Basic '

    def __init__(
        self,
        shop_id: str,
        secret_key: SecretStr,
        public_key_pem: str,
        http: httpx.AsyncClient,
        notification_url: str,
    ) -> None:
        self._shop_id = shop_id
        self._secret_key = secret_key
        self._http = http
        self._notification_url = notification_url
        loaded = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
        if not isinstance(loaded, RSAPublicKey):
            raise PaymentProviderError('BEPAID_PUBLIC_KEY must be an RSA public key')
        self._public_key = loaded

    @property
    def provider_id(self) -> str:
        return self.PROVIDER_ID

    async def start_payment(self, order: Order, return_url: str) -> PaymentStart:
        if order.currency not in self.SUPPORTED_CURRENCIES:
            raise PaymentProviderError(
                f'currency {order.currency} is unsupported here; BePaidProvider '
                f'accepts only {sorted(self.SUPPORTED_CURRENCIES)}'
            )

        success_url, decline_url = self._return_urls(return_url)
        # No payment_method.types: hosted checkout exposes every method enabled
        # for the shop (cards and ERIP included).
        body = {
            'checkout': {
                'transaction_type': 'payment',
                'test': True,
                'order': {
                    'amount': self._amount_to_minor(order.total),
                    'currency': order.currency,
                    'description': f'Order {order.order_id}',
                    'tracking_id': order.order_id,
                },
                'settings': {
                    'notification_url': self._notification_url,
                    'return_url': return_url,
                    'success_url': success_url,
                    'decline_url': decline_url,
                },
            }
        }

        try:
            response = await self._http.post(
                self.CHECKOUTS_URL,
                json=body,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-API-Version': '2',
                },
                auth=(self._shop_id, self._secret_key.get_secret_value()),
            )
        except httpx.RequestError as error:
            # httpx reports a transport-level failure - connection refused, DNS
            # failure, read timeout - by raising a RequestError subclass, which
            # carries no status code and no bePaid payload. This repository
            # already relies on that contract and names it at
            # packages/auditor/src/nodes/investigate.py:47-49 (and the Saleor
            # client / StripeProvider). There is nothing to branch on, and
            # letting it propagate would hand an httpx type across the payments
            # boundary.
            raise PaymentProviderError(
                f'start_payment could not reach bePaid: {error}'
            ) from error

        if response.status_code in self.AUTH_FAILURE_STATUSES:
            raise PaymentProviderError(
                f'start_payment was refused by bePaid: HTTP {response.status_code}'
            )
        if response.status_code >= self.HTTP_ERROR_FLOOR:
            raise PaymentProviderError(
                f'start_payment could not be completed: bePaid answered '
                f'HTTP {response.status_code}'
            )

        checkout = response.json()['checkout']
        if 'redirect_url' not in checkout or 'token' not in checkout:
            raise PaymentProviderError(
                'start_payment response is missing checkout.redirect_url or '
                'checkout.token'
            )
        return PaymentStart(
            redirect_url=checkout['redirect_url'],
            provider_reference=checkout['token'],
        )

    def parse_notification(
        self,
        payload: bytes,
        signature_header: str | None,
        basic_authorization_header: str | None,
    ) -> PaymentConfirmation:
        self._authenticate(payload, signature_header, basic_authorization_header)
        body = json.loads(payload.decode('utf-8'))
        transaction = body['transaction']
        status = transaction['status']
        if status in self.SUCCESS_STATUSES:
            succeeded = True
        elif status in self.FAILURE_STATUSES:
            succeeded = False
        else:
            raise PaymentNotificationError(
                f'bePaid notification status {status!r} is not handled'
            )
        return PaymentConfirmation(
            provider_reference=transaction['uid'],
            order_id=transaction['tracking_id'],
            amount=self._minor_to_amount(transaction['amount']),
            currency=transaction['currency'],
            succeeded=succeeded,
        )

    def _authenticate(
        self,
        payload: bytes,
        signature_header: str | None,
        basic_authorization_header: str | None,
    ) -> None:
        if signature_header is not None and signature_header.strip() != '':
            self._verify_content_signature(payload, signature_header)
            return
        if basic_authorization_header is not None and basic_authorization_header.strip() != '':
            self._verify_basic_authorization(basic_authorization_header)
            return
        raise PaymentNotificationError(
            'bePaid notification has neither Content-Signature nor Basic auth'
        )

    def _verify_content_signature(self, payload: bytes, signature_header: str) -> None:
        signature = base64.b64decode(signature_header)
        try:
            self._public_key.verify(
                signature,
                payload,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature as error:
            # cryptography.hazmat RSAPublicKey.verify documents that a mismatch
            # raises InvalidSignature
            # (https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/).
            # There is no boolean return; catching and mapping to
            # PaymentNotificationError is the verification result itself.
            raise PaymentNotificationError(
                'Content-Signature verification failed'
            ) from error

    def _verify_basic_authorization(self, header: str) -> None:
        if not header.startswith(self.BASIC_PREFIX):
            raise PaymentNotificationError('Basic authorization header is malformed')
        encoded = header[len(self.BASIC_PREFIX) :]
        decoded = base64.b64decode(encoded).decode('utf-8')
        separator = decoded.find(':')
        if separator < 0:
            raise PaymentNotificationError('Basic authorization header is malformed')
        username = decoded[:separator]
        password = decoded[separator + 1 :]
        shop_ok = hmac.compare_digest(username, self._shop_id)
        secret_ok = hmac.compare_digest(password, self._secret_key.get_secret_value())
        if not (shop_ok and secret_ok):
            raise PaymentNotificationError('Basic authorization verification failed')

    @staticmethod
    def _return_urls(return_url: str) -> tuple[str, str]:
        return (
            BePaidProvider._with_query(return_url, 'checkout', 'success'),
            BePaidProvider._with_query(return_url, 'checkout', 'decline'),
        )

    @staticmethod
    def _with_query(url: str, key: str, value: str) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query[key] = value
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    @classmethod
    def _amount_to_minor(cls, amount: Decimal) -> int:
        scaled = amount * cls.MINOR_UNITS_PER_MAJOR
        if scaled != scaled.to_integral_value():
            raise PaymentProviderError(
                f'amount {amount} has more decimal places than BYN/USD/EUR allow'
            )
        return int(scaled)

    @classmethod
    def _minor_to_amount(cls, minor: int) -> Decimal:
        return Decimal(minor) / cls.MINOR_UNITS_PER_MAJOR
