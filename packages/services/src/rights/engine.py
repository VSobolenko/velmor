from __future__ import annotations

from collections.abc import Sequence

from packages.services.src.domain.license import LicenseGrant
from packages.services.src.domain.rights import RightsAction
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.src.rights.rights_resolver import RightsResolver


class RightsEngine:
    """What Velmor is allowed to sell, as one object.

    Composition rather than inheritance: the matrix, the resolver and the gate
    stay separately testable, while a caller gets a single thing that answers
    "may this be published, and why?". Every caller that needs a verdict goes
    through here, so there is exactly one place where that question is answered.
    """

    STOREFRONT_ACTIONS: tuple[RightsAction, ...] = (
        RightsAction.RESELL,
        RightsAction.REDISTRIBUTE,
    )
    """What the storefront does with a listed good.

    Deliberately not ``MODIFY`` or ``SUBLICENSE``: Velmor lists a work as it
    arrived and does not grant buyers rights it may not hold itself. A caller
    asking a different question - the B2B verification API, say - passes its own
    action set to the resolver.
    """

    def __init__(self, grants: Sequence[LicenseGrant]) -> None:
        self.matrix = LicenseMatrix(grants)
        self.resolver = RightsResolver(self.matrix)
        self.gate = PublicationGate(self.matrix)
