from __future__ import annotations

from datetime import date

import pytest

from packages.services.src.commerce.disclosure import SellerDisclosureCheck
from packages.services.src.domain.seller import SellerDisclosure, SellerDisclosureItem

COMPLETE_FIELDS: dict[str, object] = {
    'legal_name': 'Velmor LLC',
    'registration_number': '100200300',
    'registration_date': date(2026, 1, 15),
    'registration_authority': 'Minsk City Executive Committee',
    'shop_register_number': 'SHOP-1',
    'postal_address': 'Minsk, Belarus',
    'working_hours': 'Mon-Fri 09:00-18:00',
    'contact_details': 'support@velmor.example',
    'payment_rules': 'Payment by card at checkout',
    'return_rules': 'Digital goods are not returnable after download',
    'payment_system_marks': ('visa', 'mastercard'),
}

DECLARATION_ORDER: tuple[SellerDisclosureItem, ...] = (
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

ITEMS: tuple[SellerDisclosureItem, ...] = tuple(SellerDisclosureItem)


def build_disclosure(**overrides: object) -> SellerDisclosure:
    return SellerDisclosure(**{**COMPLETE_FIELDS, **overrides})


def build_disclosure_missing(item: SellerDisclosureItem) -> SellerDisclosure:
    blanked: object = () if item is SellerDisclosureItem.PAYMENT_SYSTEM_MARKS else None
    return SellerDisclosure(**{**COMPLETE_FIELDS, item.value: blanked})


@pytest.fixture
def check() -> SellerDisclosureCheck:
    return SellerDisclosureCheck()


class TestSellerDisclosureCheck:
    def test_a_complete_disclosure_has_nothing_missing(self, check: SellerDisclosureCheck) -> None:
        assert check.incomplete(build_disclosure()) == ()

    def test_the_empty_disclosure_names_every_item(self, check: SellerDisclosureCheck) -> None:
        assert check.incomplete(SellerDisclosure()) == DECLARATION_ORDER

    def test_an_absent_disclosure_names_every_item_in_declaration_order(
        self, check: SellerDisclosureCheck
    ) -> None:
        assert check.incomplete(None) == DECLARATION_ORDER

    def test_every_declared_item_is_required(self, check: SellerDisclosureCheck) -> None:
        assert set(check.incomplete(None)) == set(SellerDisclosureItem)
        assert len(check.incomplete(None)) == 11

    @pytest.mark.parametrize('item', ITEMS, ids=[item.value for item in ITEMS])
    def test_each_missing_item_is_named_on_its_own(
        self, check: SellerDisclosureCheck, item: SellerDisclosureItem
    ) -> None:
        assert check.incomplete(build_disclosure_missing(item)) == (item,)

    def test_missing_items_keep_the_declaration_order(
        self, check: SellerDisclosureCheck
    ) -> None:
        blanked = {
            **COMPLETE_FIELDS,
            'payment_rules': None,
            'legal_name': None,
            'working_hours': None,
        }

        assert check.incomplete(SellerDisclosure(**blanked)) == (
            SellerDisclosureItem.LEGAL_NAME,
            SellerDisclosureItem.WORKING_HOURS,
            SellerDisclosureItem.PAYMENT_RULES,
        )

    def test_an_empty_marks_tuple_is_missing(self, check: SellerDisclosureCheck) -> None:
        assert check.incomplete(build_disclosure(payment_system_marks=())) == (
            SellerDisclosureItem.PAYMENT_SYSTEM_MARKS,
        )

    def test_configured_marks_are_not_missing(self, check: SellerDisclosureCheck) -> None:
        assert check.incomplete(build_disclosure(payment_system_marks=('visa',))) == ()

    def test_a_blank_string_is_not_missing(self, check: SellerDisclosureCheck) -> None:
        assert check.incomplete(build_disclosure(legal_name='')) == ()

    def test_a_whitespace_only_string_is_not_missing(self, check: SellerDisclosureCheck) -> None:
        assert check.incomplete(build_disclosure(postal_address='   ')) == ()

    def test_the_missing_items_are_members_with_the_persisted_tokens(
        self, check: SellerDisclosureCheck
    ) -> None:
        missing = check.incomplete(None)

        assert all(isinstance(item, SellerDisclosureItem) for item in missing)
        assert tuple(item.value for item in missing) == (
            'legal_name',
            'registration_number',
            'registration_date',
            'registration_authority',
            'shop_register_number',
            'postal_address',
            'working_hours',
            'contact_details',
            'payment_rules',
            'return_rules',
            'payment_system_marks',
        )
