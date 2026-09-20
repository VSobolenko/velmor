"""Dev-only stub payment provider for end-to-end checkout without live rails.

Confirmation arrives only from an authenticated ``POST /webhooks/stub``
notification, never from the buyer return URL. Production must not wire this
provider into ``CheckoutService``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import SecretStr

from packages.services.src.domain.order import Order
from packages.services.src.payments.errors import PaymentNotificationError
from packages.services.src.payments.protocol import PaymentConfirmation, PaymentStart


class StubPaymentProvider:
    """PaymentProvider that redirects straight back and settles via HMAC webhook."""

    PROVIDER_ID = 'stub'
    SIGNATURE_HEADER = 'X-Stub-Signature'

    def __init__(self, webhook_secret: SecretStr) -> None:
        self._webhook_secret = webhook_secret

    @property
    def provider_id(self) -> str:
        return self.PROVIDER_ID

    async def start_payment(self, order: Order, return_url: str) -> PaymentStart:
        return PaymentStart(
            redirect_url=self._with_order_id(return_url, order.order_id),
            provider_reference=f'stub-{order.order_id}',
        )

    def parse_notification(
        self, payload: bytes, signature_header: str
    ) -> PaymentConfirmation:
        self._verify_signature(payload, signature_header)
        body = json.loads(payload.decode('utf-8'))
        return PaymentConfirmation(
            provider_reference=body['provider_reference'],
            order_id=body['order_id'],
            amount=Decimal(str(body['amount'])),
            currency=body['currency'],
            succeeded=body['succeeded'],
        )

    def _verify_signature(self, payload: bytes, signature_header: str) -> None:
        if signature_header.strip() == '':
            raise PaymentNotificationError('X-Stub-Signature header is missing')
        expected = hmac.new(
            self._webhook_secret.get_secret_value().encode('utf-8'),
            payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature_header.strip()):
            raise PaymentNotificationError('X-Stub-Signature verification failed')

    @staticmethod
    def _with_order_id(return_url: str, order_id: str) -> str:
        parts = urlsplit(return_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query['order_id'] = order_id
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
