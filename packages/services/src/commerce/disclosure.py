from __future__ import annotations

from packages.services.src.domain.seller import SellerDisclosure, SellerDisclosureItem


class SellerDisclosureCheck:
    """Name the required seller disclosure items that are still unconfigured.

    The disclosure is stored data, not a setting (design D7), so completeness is
    answered when checkout asks rather than at bootstrap: an incomplete
    disclosure is a representable state that checkout refuses on. This class is
    the one home of that question.

    ``incomplete`` returns the missing items in the declaration order of
    ``SellerDisclosureItem``, so the same disclosure always yields the same
    tuple and an operator message reads in a stable order. An empty tuple means
    the disclosure is complete; there is no separate ``complete`` predicate. A
    ``None`` disclosure is the row that does not exist yet, and every item is
    missing.
    """

    REQUIRED_ITEMS: tuple[SellerDisclosureItem, ...] = (
        SellerDisclosureItem.LEGAL_NAME,
        SellerDisclosureItem.REGISTRATION_NUMBER,
        SellerDisclosureItem.REGISTRATION_DATE,
        SellerDisclosureItem.REGISTRATION_AUTHORITY,
        SellerDisclosureItem.SHOP_REGISTER_NUMBER,
        SellerDisclosureItem.POSTAL_ADDRESS,
        SellerDisclosureItem.WORKING_HOURS,
        SellerDisclosureItem.CONTACT_DETAILS,
        SellerDisclosureItem.PAYMENT_RULES,
        SellerDisclosureItem.RETURN_RULES,
        SellerDisclosureItem.PAYMENT_SYSTEM_MARKS,
    )

    def incomplete(self, disclosure: SellerDisclosure | None) -> tuple[SellerDisclosureItem, ...]:
        if disclosure is None:
            return self.REQUIRED_ITEMS
        return tuple(item for item in self.REQUIRED_ITEMS if self._is_missing(disclosure, item))

    @staticmethod
    def _is_missing(disclosure: SellerDisclosure, item: SellerDisclosureItem) -> bool:
        if item is SellerDisclosureItem.PAYMENT_SYSTEM_MARKS:
            return disclosure.payment_system_marks == ()
        # The item token is the field name, so the attribute name is data here.
        return getattr(disclosure, item.value) is None
