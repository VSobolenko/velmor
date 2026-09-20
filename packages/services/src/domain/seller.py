from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class SellerDisclosureItem(StrEnum):
    """One item of the seller identity a payment provider requires the shop to publish.

    The token is the field name on ``SellerDisclosure``, the string the
    completeness check reports, and eventually the string the storefront shows,
    so a rename is a defect rather than a refactor.
    """

    LEGAL_NAME = 'legal_name'
    REGISTRATION_NUMBER = 'registration_number'
    REGISTRATION_DATE = 'registration_date'
    REGISTRATION_AUTHORITY = 'registration_authority'
    SHOP_REGISTER_NUMBER = 'shop_register_number'
    POSTAL_ADDRESS = 'postal_address'
    WORKING_HOURS = 'working_hours'
    CONTACT_DETAILS = 'contact_details'
    PAYMENT_RULES = 'payment_rules'
    RETURN_RULES = 'return_rules'
    PAYMENT_SYSTEM_MARKS = 'payment_system_marks'


class SellerDisclosure(BaseModel):
    """The seller's legal identity as the operator has configured it.

    Every field is optional and carries an explicit default because an
    incomplete disclosure is a state the system has to represent: the storefront
    keeps checkout unavailable while an item is missing and names it, rather
    than refusing to start (design D7). The row is written by an operator
    command, and each field is absent until that command supplies it, so
    ``SellerDisclosure()`` is the honest wholly-unconfigured disclosure.

    ``registration_date`` is a date and not a timestamp: a registration has no
    time of day. ``payment_system_marks`` is a tuple that is allowed to be
    empty rather than an optional field, because "no marks configured" is an
    empty tuple and the completeness check treats it as missing.
    """

    model_config = {'frozen': True}

    legal_name: str | None = None
    registration_number: str | None = None
    registration_date: date | None = None
    registration_authority: str | None = None
    shop_register_number: str | None = None
    postal_address: str | None = None
    working_hours: str | None = None
    contact_details: str | None = None
    payment_rules: str | None = None
    return_rules: str | None = None
    payment_system_marks: tuple[str, ...] = ()
