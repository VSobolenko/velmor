from __future__ import annotations

from packages.core.src.bootstrap.platform_settings import PlatformSettings
from packages.core.src.bootstrap.settings_loader import SettingsLoader


class ScoutSettings(PlatformSettings):
    """Everything the discovery agent needs beyond the platform baseline."""

    def __init__(self, loader: SettingsLoader) -> None:
        super().__init__(loader)
        self.scout_queries: tuple[str, ...] = tuple(loader.required_str_list('SCOUT_QUERIES'))
        self.scout_page_limit: int = loader.required_int('SCOUT_PAGE_LIMIT')
        self.scout_interval_seconds: int = loader.required_int('SCOUT_INTERVAL_SECONDS')
        self.scout_concurrency: int = loader.required_int('SCOUT_CONCURRENCY')
