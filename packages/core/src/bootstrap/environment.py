from __future__ import annotations

from enum import StrEnum


class Environment(StrEnum):
    """Deployment profile. Each profile maps to its own ``.env.<profile>`` file."""

    DEV = 'dev'
    STAGE = 'stage'
    PROD = 'prod'
    TEST = 'test'
