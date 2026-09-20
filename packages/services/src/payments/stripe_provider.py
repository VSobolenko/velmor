"""Stripe Checkout Session payment provider (test mode).

Live Stripe keys (``sk_live_`` / live webhook secrets) are out of scope for this
module. Callers must supply test-mode credentials. Confirmation arrives only from
an authenticated webhook notification, never from the buyer return URL.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import SecretStr

from packages.services.src.domain.order import Order
from packages.services.src.payments.errors import (
    PaymentNotificationError,
    PaymentProviderError,
)
from packages.services.src.payments.protocol import PaymentConfirmation, PaymentStart


class StripeProvider:
    """PaymentProvider for Stripe Checkout Sessions via httpx.

    Webhook authenticity uses Stripe's documented HMAC-SHA256 scheme
    (https://docs.stripe.com/webhooks#verify-manually): signed_payload is
    ``{timestamp}.{raw_body}``, keyed by the endpoint signing secret, compared
    with constant-time equality against each ``v1`` signature in
    ``Stripe-Signature``.
    """

    PROVIDER_ID = 'stripe'
    SESSIONS_URL = 'https://api.stripe.com/v1/checkout/sessions'
    AUTH_FAILURE_STATUSES = frozenset({401, 403})
    HTTP_ERROR_FLOOR = 400
    SUPPORTED_CURRENCIES = frozenset({'USD', 'EUR'})
    CENTS_PER_UNIT = Decimal(100)
    SIGNATURE_TOLERANCE_SECONDS = 300
    EXPECTED_SCHEME = 'v1'
    COMPLETED_EVENT = 'checkout.session.completed'
    EXPIRED_EVENT = 'checkout.session.expired'

    def __init__(
        self,
        secret_key: SecretStr,
        webhook_secret: SecretStr,
        http: httpx.AsyncClient,
    ) -> None:
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret
        self._http = http

    @property
    def provider_id(self) -> str:
        return self.PROVIDER_ID

    async def start_payment(self, order: Order, return_url: str) -> PaymentStart:
        if order.currency not in self.SUPPORTED_CURRENCIES:
            raise PaymentProviderError(
                f'currency {order.currency} is unsupported here; StripeProvider '
                f'accepts only {sorted(self.SUPPORTED_CURRENCIES)}'
            )

        success_url, cancel_url = self._return_urls(return_url)
        form: dict[str, str] = {
            'mode': 'payment',
            'success_url': success_url,
            'cancel_url': cancel_url,
            'client_reference_id': order.order_id,
            'metadata[order_id]': order.order_id,
        }
        for index, line in enumerate(order.lines):
            form[f'line_items[{index}][price_data][currency]'] = order.currency.lower()
            form[f'line_items[{index}][price_data][unit_amount]'] = str(
                self._amount_to_cents(line.unit_amount)
            )
            form[f'line_items[{index}][price_data][product_data][name]'] = line.candidate_id
            form[f'line_items[{index}][quantity]'] = str(line.quantity)

        try:
            response = await self._http.post(
                self.SESSIONS_URL,
                data=form,
                headers={
                    'Authorization': f'Bearer {self._secret_key.get_secret_value()}',
                },
            )
        except httpx.RequestError as error:
            # httpx reports a transport-level failure - connection refused, DNS
            # failure, read timeout - by raising a RequestError subclass, which
            # carries no status code and no Stripe payload. This repository
            # already relies on that contract and names it at
            # packages/auditor/src/nodes/investigate.py:47-49 (and the Saleor
            # client). There is nothing to branch on, and letting it propagate
            # would hand an httpx type across the payments boundary.
            raise PaymentProviderError(
                f'start_payment could not reach Stripe: {error}'
            ) from error

        if response.status_code in self.AUTH_FAILURE_STATUSES:
            raise PaymentProviderError(
                f'start_payment was refused by Stripe: HTTP {response.status_code}'
            )
        if response.status_code >= self.HTTP_ERROR_FLOOR:
            raise PaymentProviderError(
                f'start_payment could not be completed: Stripe answered '
                f'HTTP {response.status_code}'
            )

        session = response.json()
        return PaymentStart(
            redirect_url=session['url'],
            provider_reference=session['id'],
        )

    def parse_notification(self, payload: bytes, signature_header: str) -> PaymentConfirmation:
        self._verify_signature(payload, signature_header)
        event = json.loads(payload.decode('utf-8'))
        event_type = event['type']
        if event_type == self.COMPLETED_EVENT:
            succeeded = True
        elif event_type == self.EXPIRED_EVENT:
            # Documented failure path: the Checkout Session expired unpaid.
            succeeded = False
        else:
            raise PaymentNotificationError(
                f'Stripe notification event type {event_type!r} is not handled'
            )

        session = event['data']['object']
        order_id = session['client_reference_id']
        if order_id is None:
            order_id = session['metadata']['order_id']
        amount_total = session['amount_total']
        currency = session['currency'].upper()
        return PaymentConfirmation(
            provider_reference=session['id'],
            order_id=order_id,
            amount=self._cents_to_amount(amount_total),
            currency=currency,
            succeeded=succeeded,
        )

    def _verify_signature(self, payload: bytes, signature_header: str) -> None:
        if signature_header.strip() == '':
            raise PaymentNotificationError('Stripe-Signature header is missing')

        timestamp, signatures = self._parse_signature_header(signature_header)
        if not signatures:
            raise PaymentNotificationError(
                f'no {self.EXPECTED_SCHEME} signatures found in Stripe-Signature'
            )

        age = abs(int(time.time()) - timestamp)
        if age > self.SIGNATURE_TOLERANCE_SECONDS:
            raise PaymentNotificationError(
                f'Stripe-Signature timestamp is outside tolerance ({age}s)'
            )

        signed_payload = f'{timestamp}.{payload.decode("utf-8")}'
        expected = hmac.new(
            self._webhook_secret.get_secret_value().encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, signature) for signature in signatures):
            raise PaymentNotificationError('Stripe-Signature verification failed')

    def _parse_signature_header(self, header: str) -> tuple[int, tuple[str, ...]]:
        timestamp: int | None = None
        signatures: list[str] = []
        for element in header.split(','):
            parts = element.split('=', 1)
            if len(parts) != 2:
                continue
            prefix, value = parts
            if prefix == 't':
                timestamp = int(value)
            elif prefix == self.EXPECTED_SCHEME:
                signatures.append(value)
        if timestamp is None:
            raise PaymentNotificationError(
                'Stripe-Signature header has no timestamp'
            )
        return timestamp, tuple(signatures)

    @staticmethod
    def _return_urls(return_url: str) -> tuple[str, str]:
        # success_url / cancel_url are derived from return_url by appending
        # checkout=success|cancel so the buyer return page can distinguish the
        # two outcomes. Settlement still requires the authenticated webhook.
        return (
            StripeProvider._with_query(return_url, 'checkout', 'success'),
            StripeProvider._with_query(return_url, 'checkout', 'cancel'),
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
    def _amount_to_cents(cls, amount: Decimal) -> int:
        scaled = amount * cls.CENTS_PER_UNIT
        if scaled != scaled.to_integral_value():
            raise PaymentProviderError(
                f'amount {amount} has more decimal places than USD/EUR allow'
            )
        return int(scaled)

    @classmethod
    def _cents_to_amount(cls, cents: int) -> Decimal:
        return Decimal(cents) / cls.CENTS_PER_UNIT
