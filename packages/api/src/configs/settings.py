from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from pydantic import SecretStr

from packages.core.src.bootstrap.platform_settings import PlatformSettings
from packages.core.src.bootstrap.settings_loader import SettingsLoader


class CommerceSettings(PlatformSettings):
    """Everything the storefront process needs beyond the platform baseline.

    The Saleor client, the payment providers and the delivery service are wired
    from these values and never read the environment themselves. Secrets stay
    ``SecretStr`` here; the consumer reveals one at the point of use.
    """

    def __init__(self, loader: SettingsLoader) -> None:
        super().__init__(loader)
        self.saleor_api_url: str = loader.required_str('SALEOR_API_URL')
        self.saleor_app_token: SecretStr = loader.required_secret('SALEOR_APP_TOKEN')
        self.stripe_secret_key: SecretStr = loader.required_secret('STRIPE_SECRET_KEY')
        self.stripe_webhook_signing_secret: SecretStr = loader.required_secret(
            'STRIPE_WEBHOOK_SIGNING_SECRET'
        )
        self.bepaid_shop_id: str = loader.required_str('BEPAID_SHOP_ID')
        self.bepaid_secret_key: SecretStr = loader.required_secret('BEPAID_SECRET_KEY')
        self.bepaid_public_key: str = loader.required_str('BEPAID_PUBLIC_KEY')
        self.bepaid_notification_url: str = loader.required_str('BEPAID_NOTIFICATION_URL')
        self.stub_webhook_secret: SecretStr = loader.required_secret('STUB_WEBHOOK_SECRET')
        self.operator_refund_key: SecretStr = loader.required_secret('OPERATOR_REFUND_KEY')
        self.storefront_domain: str = loader.required_str('STOREFRONT_DOMAIN')
        self.delivery_grant_secret: SecretStr = loader.required_secret(
            'DELIVERY_GRANT_SECRET'
        )
        self.delivery_grant_lifetime_seconds: int = loader.required_int(
            'DELIVERY_GRANT_LIFETIME_SECONDS'
        )
        self.delivery_cache_max_bytes: int = loader.required_int('DELIVERY_CACHE_MAX_BYTES')
        self.delivery_cache_dir: Path = loader.required_path('DELIVERY_CACHE_DIR')
        # Flat catalogue price until per-good pricing exists on CatalogueEntry.
        self.catalogue_unit_amount: Decimal = Decimal(
            loader.required_str('CATALOGUE_UNIT_AMOUNT')
        )
        self.catalogue_currency: str = loader.required_str('CATALOGUE_CURRENCY')
        # Buyer accounts. The lifetime is the session's, the cookie's and the
        # stored expiry together, so there is one number to change.
        self.session_cookie_name: str = loader.required_str('SESSION_COOKIE_NAME')
        self.session_lifetime_seconds: int = loader.required_int(
            'SESSION_LIFETIME_SECONDS'
        )
        self.password_min_length: int = loader.required_int('PASSWORD_MIN_LENGTH')
        self.failed_attempt_limit: int = loader.required_int('FAILED_ATTEMPT_LIMIT')
        self.failed_attempt_window_seconds: int = loader.required_int(
            'FAILED_ATTEMPT_WINDOW_SECONDS'
        )
