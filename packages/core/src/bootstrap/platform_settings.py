from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from packages.core.src.bootstrap.environment import Environment
from packages.core.src.bootstrap.settings_loader import SettingsLoader


class PlatformSettings:
    """Settings every Velmor process needs, regardless of which agent it runs.

    Agent-specific settings subclass this and read their own variables.
    """

    def __init__(self, loader: SettingsLoader) -> None:
        self.loader: SettingsLoader = loader
        self.env_file: Path = loader.env_file
        self.environment: str = loader.required_str('ENVIRONMENT')
        self.database_url: SecretStr = loader.required_secret('DATABASE_URL')
        self.redis_url: str = loader.required_str('REDIS_URL')
        self.logfire_token: SecretStr = loader.required_secret('LOGFIRE_TOKEN')

    @property
    def profile(self) -> Environment:
        return Environment(self.environment)

    @property
    def logfire_enabled(self) -> bool:
        """Tracing is off in tests so a unit run never ships spans."""
        return self.profile is not Environment.TEST

    @property
    def database_dsn(self) -> str:
        return self.database_url.get_secret_value()
