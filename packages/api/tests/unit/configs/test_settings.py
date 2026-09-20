from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from packages.api.src.configs.settings import CommerceSettings
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.core.src.errors import ConfigurationError


class TestCommerceSettings:
    """Bootstrap behaviour: every variable is required, every secret stays hidden."""

    BASELINE_VALUES = {
        'ENVIRONMENT': 'test',
        'DATABASE_URL': 'postgresql+asyncpg://velmor:velmor@localhost:5432/velmor',
        'REDIS_URL': 'redis://localhost:6379/0',
        'LOGFIRE_TOKEN': 'logfire-token-literal',
    }

    COMMERCE_VALUES = {
        'SALEOR_API_URL': 'https://saleor.example.test/graphql/',
        'SALEOR_APP_TOKEN': 'saleor-app-token-literal',
        'STRIPE_SECRET_KEY': 'stripe-secret-key-literal',
        'STRIPE_WEBHOOK_SIGNING_SECRET': 'stripe-webhook-secret-literal',
        'BEPAID_SHOP_ID': 'bepaid-shop-id-literal',
        'BEPAID_SECRET_KEY': 'bepaid-secret-key-literal',
        'BEPAID_PUBLIC_KEY': '-----BEGIN PUBLIC KEY----- test-pem -----END PUBLIC KEY-----',
        'BEPAID_NOTIFICATION_URL': 'https://shop.example.test/webhooks/bepaid',
        'OPERATOR_REFUND_KEY': 'operator-refund-key-literal',
        'STOREFRONT_DOMAIN': 'shop.example.test',
        'DELIVERY_GRANT_SECRET': 'delivery-grant-secret-literal',
        'DELIVERY_GRANT_LIFETIME_SECONDS': '900',
        'DELIVERY_CACHE_MAX_BYTES': '268435456',
        'DELIVERY_CACHE_DIR': 'var/delivery-cache',
    }

    SECRET_FIELDS = {
        'saleor_app_token': 'SALEOR_APP_TOKEN',
        'stripe_secret_key': 'STRIPE_SECRET_KEY',
        'stripe_webhook_signing_secret': 'STRIPE_WEBHOOK_SIGNING_SECRET',
        'bepaid_secret_key': 'BEPAID_SECRET_KEY',
        'operator_refund_key': 'OPERATOR_REFUND_KEY',
        'delivery_grant_secret': 'DELIVERY_GRANT_SECRET',
    }

    @pytest.mark.parametrize('variable', tuple(COMMERCE_VALUES))
    def test_a_missing_variable_fails_bootstrap_naming_the_key(
        self, variable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        present = {**self.BASELINE_VALUES, **self.COMMERCE_VALUES}
        del present[variable]
        env_file = self._write_env_file(tmp_path, present)
        self._export(monkeypatch, present)
        monkeypatch.delenv(variable, raising=False)

        with pytest.raises(ConfigurationError, match=variable):
            CommerceSettings(SettingsLoader(env_file))

    def test_every_variable_lands_on_its_field_with_the_loader_type(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = self._load(tmp_path, monkeypatch)

        assert settings.saleor_api_url == self.COMMERCE_VALUES['SALEOR_API_URL']
        assert settings.bepaid_shop_id == self.COMMERCE_VALUES['BEPAID_SHOP_ID']
        assert settings.bepaid_public_key == self.COMMERCE_VALUES['BEPAID_PUBLIC_KEY']
        assert settings.bepaid_notification_url == self.COMMERCE_VALUES[
            'BEPAID_NOTIFICATION_URL'
        ]
        assert settings.storefront_domain == self.COMMERCE_VALUES['STOREFRONT_DOMAIN']
        assert settings.delivery_grant_lifetime_seconds == 900
        assert settings.delivery_cache_max_bytes == 268435456
        assert settings.delivery_cache_dir == Path(self.COMMERCE_VALUES['DELIVERY_CACHE_DIR'])

    def test_the_secret_fields_are_secret_str(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = self._load(tmp_path, monkeypatch)

        for field in self.SECRET_FIELDS:
            assert isinstance(getattr(settings, field), SecretStr)

    def test_no_secret_literal_appears_in_any_attribute_representation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = self._load(tmp_path, monkeypatch)
        secrets = tuple(self.COMMERCE_VALUES[variable] for variable in self.SECRET_FIELDS.values())
        representations = tuple(repr(value) for value in vars(settings).values())

        for secret in secrets:
            assert secret not in repr(settings)
            assert all(secret not in representation for representation in representations)

    def _load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CommerceSettings:
        values = {**self.BASELINE_VALUES, **self.COMMERCE_VALUES}
        env_file = self._write_env_file(tmp_path, values)
        self._export(monkeypatch, values)
        return CommerceSettings(SettingsLoader(env_file))

    def _write_env_file(self, tmp_path: Path, values: dict[str, str]) -> Path:
        env_file = tmp_path / '.env.test'
        env_file.write_text('\n'.join(f'{key}={value}' for key, value in values.items()))
        return env_file

    def _export(self, monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
        for key, value in values.items():
            monkeypatch.setenv(key, value)
