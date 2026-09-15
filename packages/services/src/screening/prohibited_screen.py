from __future__ import annotations

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.screening import ScreeningResult


class ProhibitedCategoryScreen:
    """Reject goods whose *category* makes them untradeable, whatever their license.

    A permissive license on an activation key does not make activation keys
    sellable: payment providers prohibit the trade, and the platform refuses it
    outright. This is a keyword backstop, not the primary control. The primary
    control is the source registry: Velmor only crawls sources that do not carry
    these goods in the first place, and this screen exists so a mislabelled item
    that slips through the funnel still cannot reach the catalog.
    """

    PROHIBITED_TERMS: tuple[str, ...] = (
        'license key',
        'product key',
        'activation key',
        'serial key',
        'registration key',
        'keygen',
        'crack',
        'nulled',
        'premium account',
        'shared account',
        'account credentials',
        'subscription',
        'gift card',
        'voucher code',
        'game key',
        'steam key',
    )

    def screen(self, candidate: Candidate) -> ScreeningResult:
        haystack = ' '.join(
            (candidate.title, candidate.content_type, candidate.declared_license_text or '')
        ).lower()
        violations = tuple(term for term in self.PROHIBITED_TERMS if term in haystack)
        return ScreeningResult(
            candidate_id=candidate.id,
            clear=not violations,
            violations=violations,
        )
