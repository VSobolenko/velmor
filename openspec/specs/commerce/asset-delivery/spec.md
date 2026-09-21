# commerce/asset-delivery Specification

## Purpose

Delivers the purchased file to its buyer, from us, without disclosing where the file came from.

## Requirements

### Requirement: Delivery requires a valid entitlement
A download SHALL be served only to the buyer who holds a valid entitlement for that good. Any other request SHALL be refused.

#### Scenario: An entitled buyer downloads
- **WHEN** a buyer holding a valid entitlement requests the good
- **THEN** the good's file is delivered

#### Scenario: A request without an entitlement is refused
- **WHEN** a request for a good arrives without a valid entitlement
- **THEN** it is refused
- **AND** no part of the file is served

#### Scenario: A revoked entitlement is refused
- **WHEN** an entitlement has been revoked and its buyer requests the good
- **THEN** the request is refused with a reason

### Requirement: The origin of the file is not disclosed to the buyer
No page and no response served to the buyer SHALL contain the origin address of the file.

#### Scenario: The origin address is absent from what the buyer receives
- **WHEN** a buyer opens the product page and the download response
- **THEN** neither contains the origin address of the file

### Requirement: Download links are short-lived and bound to the buyer
A download link SHALL expire. An expired or misused link SHALL be refused with a reason, and the buyer SHALL be able to obtain a fresh link from their account.

#### Scenario: An expired link is refused and can be replaced
- **WHEN** an expired link is used
- **THEN** it is refused with a reason
- **AND** the buyer can obtain a fresh one from their account

#### Scenario: A link alone is not sufficient
- **WHEN** a link is used by someone other than the buyer it was issued to
- **THEN** it is refused

### Requirement: An unavailable origin fails visibly rather than substituting
When the origin is unavailable or returns an error, delivery SHALL fail with a reason the buyer can see. The system SHALL NOT serve a substitute file, a partial file, or an error page in place of the good.

#### Scenario: An unavailable origin does not deliver a wrong file
- **WHEN** the origin is unreachable or returns an error
- **THEN** the delivery fails with a reason the buyer can see
- **AND** nothing is recorded as delivered

### Requirement: The file delivered is the file the record was established for
The file delivered SHALL be the file the good's record was established for. When the origin's response does not match what is recorded for the good, delivery SHALL fail rather than serve it.

#### Scenario: A changed file at the origin is not served
- **WHEN** the origin returns content that does not match what is recorded for the good
- **THEN** the delivery fails with a reason
- **AND** the buyer's entitlement remains valid

### Requirement: Attribution travels with the good
The download page SHALL show the license identity and the obligations recorded for the good, so that an attribution requirement is met at the point where the buyer receives the file.

#### Scenario: Attribution is present where the file is delivered
- **WHEN** a buyer reaches the download of a good whose `RightsRecord` carries attribution obligations
- **THEN** the license identity and those obligations are shown with the download
