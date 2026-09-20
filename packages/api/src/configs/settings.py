from __future__ import annotations

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
        self.storefront_domain: str = loader.required_str('STOREFRONT_DOMAIN')
        self.delivery_grant_lifetime_seconds: int = loader.required_int(
            'DELIVERY_GRANT_LIFETIME_SECONDS'
        )
        self.delivery_cache_max_bytes: int = loader.required_int('DELIVERY_CACHE_MAX_BYTES')
        self.delivery_cache_dir: Path = loader.required_path('DELIVERY_CACHE_DIR')
