# commerce/storefront Specification

## Purpose

The customer-facing shop over the goods that passed the gate: browsing, product pages, cart, account, and the seller disclosure a payment provider requires of the site.

## Requirements

### Requirement: The storefront shows only catalogued goods
Product pages and category listings SHALL show only goods present in the catalogue. A request for a good that is not in the catalogue SHALL be answered as not found.

#### Scenario: A withdrawn good is not reachable by direct address
- **WHEN** a buyer requests the product page of a good that is not in the catalogue
- **THEN** the response is not found
- **AND** no price and no file is disclosed

### Requirement: A product page states the licence and the attribution
A product page SHALL display, before purchase, the license identity and every obligation recorded for the good.

#### Scenario: An attribution licence shows its attribution
- **WHEN** a good's `RightsRecord` carries attribution obligations
- **THEN** the product page shows the license identity and those obligations

#### Scenario: A licence with no obligations still shows its identity
- **WHEN** a good's `RightsRecord` carries no obligations
- **THEN** the product page still shows the license identity

### Requirement: Browsing by category
The storefront SHALL present the categories and the goods within them.

#### Scenario: A category lists its goods
- **WHEN** a buyer opens a category that contains catalogue entries
- **THEN** the goods in that category are listed
- **AND** each price shown is the price the checkout would charge

#### Scenario: An empty category is shown as empty
- **WHEN** a buyer opens a category that contains no entries
- **THEN** the category is presented without goods
- **AND** no error is reported to the buyer

### Requirement: Cart
A cart SHALL persist for an identified buyer across sessions.

#### Scenario: A cart survives a new session
- **WHEN** an identified buyer adds a good to the cart and returns in a new session
- **THEN** the cart still contains that good

### Requirement: Account and order history
An identified buyer SHALL have an account that lists their orders and their entitlements, and SHALL be able to obtain a download for any entitlement still valid.

#### Scenario: A buyer sees a paid order
- **WHEN** one of a buyer's orders has been paid
- **THEN** the account lists that order as paid
- **AND** the purchased good can be downloaded from the account

#### Scenario: A buyer sees an unpaid order
- **WHEN** one of a buyer's orders has not been paid
- **THEN** the account lists it as unpaid
- **AND** no download is offered for it

### Requirement: Checkout requires an identifiable buyer
Checkout SHALL require a buyer that can be identified for delivery, either by an account or by an email address supplied at checkout.

#### Scenario: A buyer without an identifier cannot complete checkout
- **WHEN** a buyer reaches payment without an account and without supplying an email address
- **THEN** checkout is refused with a reason
- **AND** no payment is taken

### Requirement: Seller disclosure is required and is shown before payment
The storefront SHALL carry the seller's legal identity: legal name, registration number, registration date and authority, online-shop register number, postal address, working hours, contact details, payment rules, return rules, and the marks of the payment systems in use. While any of these is unconfigured, checkout SHALL be unavailable.

#### Scenario: Checkout is unavailable while a disclosure item is missing
- **WHEN** a required seller disclosure item is not configured
- **THEN** checkout is unavailable
- **AND** the missing item is named

#### Scenario: Disclosure is presented before payment is taken
- **WHEN** the seller disclosure is configured and a buyer reaches checkout
- **THEN** the seller identity, the contact details, the payment rules and the return rules are presented before payment is taken
