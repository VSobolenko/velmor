from __future__ import annotations

from packages.core.src.errors import VelmorError


class SaleorTransportError(VelmorError):
    """Saleor could not be reached, or answered with a status the client cannot use."""


class SaleorGraphQLError(VelmorError):
    """Saleor answered HTTP 200 and reported errors in the GraphQL payload."""


class SaleorAuthError(VelmorError):
    """Saleor refused the credential."""
