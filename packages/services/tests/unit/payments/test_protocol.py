from __future__ import annotations

from decimal import Decimal

from packages.services.src.payments.protocol import PaymentConfirmation, PaymentStart


class TestPaymentProtocolModels:
    def test_payment_start_is_frozen(self) -> None:
        start = PaymentStart(
            redirect_url='https://pay.example/r',
            provider_reference='ref-1',
        )

        assert start.redirect_url == 'https://pay.example/r'
        assert start.provider_reference == 'ref-1'
        assert start.model_config.get('frozen') is True

    def test_payment_confirmation_carries_exact_amount(self) -> None:
        confirmation = PaymentConfirmation(
            provider_reference='ref-1',
            order_id='order-1',
            amount=Decimal('12.50'),
            currency='BYN',
            succeeded=True,
        )

        assert confirmation.amount == Decimal('12.50')
        assert confirmation.currency == 'BYN'
        assert confirmation.succeeded is True
        assert confirmation.model_config.get('frozen') is True
