from __future__ import annotations

from packages.core.src.errors import VelmorError


class PaymentProviderError(VelmorError):
    """The payment provider refused or could not complete a request."""


class PaymentNotificationError(VelmorError):
    """A provider notification failed authentication or could not be parsed."""
