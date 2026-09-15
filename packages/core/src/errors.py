from __future__ import annotations


class VelmorError(Exception):
    """Base class for every error Velmor raises deliberately."""


class ConfigurationError(VelmorError):
    """A required setting is missing or malformed."""


class SourceContractError(VelmorError):
    """A source connector violated its declared contract."""


class SourceNotConfiguredError(VelmorError):
    """An enabled source is missing credentials it declared as required."""


class UnknownSourceError(VelmorError):
    """A source id was used that is not in the registry."""


class RightsDeniedError(VelmorError):
    """A good was about to be published without a passing rights verdict."""


class ProhibitedCategoryError(VelmorError):
    """A candidate matches a category Velmor refuses to trade in."""
