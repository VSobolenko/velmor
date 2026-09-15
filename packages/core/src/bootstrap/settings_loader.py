from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

from packages.core.src.errors import ConfigurationError
from packages.core.src.system_utils.file_guard import FsValidator


class SettingsLoader:
    """Load one ``.env`` profile into the process environment.

    Every accessor raises :class:`ConfigurationError` when the variable is
    absent. There are no optional accessors and no fallbacks: a missing setting
    must fail here, at bootstrap, instead of silently becoming a default
    somewhere downstream.
    """

    def __init__(self, env_file: Path) -> None:
        FsValidator.validate_existing_file(env_file)
        self.env_file: Path = env_file.resolve()
        load_dotenv(self.env_file, override=True)

    def required_str(self, key: str) -> str:
        return self._read(key)

    def required_int(self, key: str) -> int:
        return int(self._read(key))

    def required_bool(self, key: str) -> bool:
        return self._read(key).upper() in ('TRUE', '1', 'YES', 'ON')

    def required_path(self, key: str) -> Path:
        return Path(self._read(key))

    def required_secret(self, key: str) -> SecretStr:
        return SecretStr(self._read(key))

    def required_str_list(self, key: str) -> list[str]:
        parts = [part.strip() for part in self._read(key).split(',') if part.strip()]
        if not parts:
            raise ConfigurationError(
                f"Required environment variable '{key}' must contain at least one value"
            )
        return parts

    def has(self, key: str) -> bool:
        """Report presence only, for contract checks over *optional* sources.

        Never use this to select a default for a platform-level setting: those go
        through the ``required_*`` accessors above.
        """
        return bool(os.getenv(key))

    def _read(self, key: str) -> str:
        value = os.getenv(key)
        if value is None:
            raise ConfigurationError(
                f"Required environment variable '{key}' is not set (loaded from {self.env_file})"
            )
        return value
