from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from packages.services.src.domain.seller import SellerDisclosure, SellerDisclosureItem

REGISTRATION_DATE = date(2026, 1, 15)


def build_disclosure(**overrides: object) -> SellerDisclosure:
    fields: dict[str, object] = {
        'legal_name': 'Velmor LLC',
        'registration_number': '100200300',
        'registration_date': REGISTRATION_DATE,
        'registration_authority': 'Minsk City Executive Committee',
        'shop_register_number': 'SHOP-1',
        'postal_address': 'Minsk, Belarus',
        'working_hours': 'Mon-Fri 09:00-18:00',
        'contact_details': 'support@velmor.example',
        'payment_rules': 'Payment by card at checkout',
        'return_rules': 'Digital goods are not returnable after download',
        'payment_system_marks': ('visa', 'mastercard'),
    }
    return SellerDisclosure(**{**fields, **overrides})


class TestSellerDisclosureItem:
    def test_there_are_exactly_the_eleven_items_the_spec_requires(self) -> None:
        assert set(SellerDisclosureItem) == {
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
        }

    @pytest.mark.parametrize(
        ('item', 'token'),
        [
            (SellerDisclosureItem.LEGAL_NAME, 'legal_name'),
            (SellerDisclosureItem.REGISTRATION_NUMBER, 'registration_number'),
            (SellerDisclosureItem.REGISTRATION_DATE, 'registration_date'),
            (SellerDisclosureItem.REGISTRATION_AUTHORITY, 'registration_authority'),
            (SellerDisclosureItem.SHOP_REGISTER_NUMBER, 'shop_register_number'),
            (SellerDisclosureItem.POSTAL_ADDRESS, 'postal_address'),
            (SellerDisclosureItem.WORKING_HOURS, 'working_hours'),
            (SellerDisclosureItem.CONTACT_DETAILS, 'contact_details'),
            (SellerDisclosureItem.PAYMENT_RULES, 'payment_rules'),
            (SellerDisclosureItem.RETURN_RULES, 'return_rules'),
            (SellerDisclosureItem.PAYMENT_SYSTEM_MARKS, 'payment_system_marks'),
        ],
    )
    def test_the_token_is_the_string_the_system_persists(
        self, item: SellerDisclosureItem, token: str
    ) -> None:
        assert item.value == token

    def test_the_item_tokens_are_the_field_names_on_the_disclosure(self) -> None:
        assert {item.value for item in SellerDisclosureItem} == set(SellerDisclosure.model_fields)


class TestSellerDisclosure:
    def test_a_complete_disclosure_carries_every_item(self) -> None:
        disclosure = build_disclosure()

        assert disclosure.legal_name == 'Velmor LLC'
        assert disclosure.registration_number == '100200300'
        assert disclosure.registration_date == REGISTRATION_DATE
        assert disclosure.registration_authority == 'Minsk City Executive Committee'
        assert disclosure.shop_register_number == 'SHOP-1'
        assert disclosure.postal_address == 'Minsk, Belarus'
        assert disclosure.working_hours == 'Mon-Fri 09:00-18:00'
        assert disclosure.contact_details == 'support@velmor.example'
        assert disclosure.payment_rules == 'Payment by card at checkout'
        assert disclosure.return_rules == 'Digital goods are not returnable after download'
        assert disclosure.payment_system_marks == ('visa', 'mastercard')

    def test_the_wholly_empty_disclosure_is_constructible(self) -> None:
        disclosure = SellerDisclosure()

        assert disclosure.legal_name is None
        assert disclosure.registration_number is None
        assert disclosure.registration_date is None
        assert disclosure.registration_authority is None
        assert disclosure.shop_register_number is None
        assert disclosure.postal_address is None
        assert disclosure.working_hours is None
        assert disclosure.contact_details is None
        assert disclosure.payment_rules is None
        assert disclosure.return_rules is None
        assert disclosure.payment_system_marks == ()

    def test_marks_are_stored_as_a_tuple(self) -> None:
        disclosure = build_disclosure(payment_system_marks=['visa', 'mastercard'])

        assert disclosure.payment_system_marks == ('visa', 'mastercard')
        assert isinstance(disclosure.payment_system_marks, tuple)

    def test_marks_are_a_tuple_and_never_none(self) -> None:
        with pytest.raises(ValidationError):
            build_disclosure(payment_system_marks=None)

    def test_a_disclosure_is_frozen(self) -> None:
        disclosure = build_disclosure()

        with pytest.raises(ValidationError):
            disclosure.legal_name = 'Other Seller'
