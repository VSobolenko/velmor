## ADDED Requirements

### Requirement: An order belongs to a signed-in buyer
The owner of an order, and of the entitlements the order creates, SHALL be the account that is signed in when the order is started. The buyer SHALL NOT be taken from a value the caller supplies in the request. A checkout started without a valid session SHALL be refused before any payment is attempted.

#### Scenario: The order records its owner as the signed-in account
- **WHEN** a signed-in buyer starts a checkout
- **THEN** the order created belongs to that buyer's account
- **AND** the entitlement created for a paid order belongs to the same account

#### Scenario: A checkout with no valid session is refused
- **WHEN** a checkout is started with no session, an expired session, or a revoked session
- **THEN** the checkout is refused as unauthenticated
- **AND** no order is created
- **AND** no payment is taken from any provider

#### Scenario: A caller cannot name the owner
- **WHEN** a checkout is started by a signed-in buyer and the request also carries an identifier claiming a different buyer
- **THEN** the order still belongs to the signed-in account
- **AND** the caller-supplied identifier does not become the owner

#### Scenario: One account cannot read another's order
- **WHEN** a signed-in buyer requests an order that belongs to a different account
- **THEN** the request is refused as not found
- **AND** nothing about that order, its lines or its entitlement is returned

### Requirement: The gate is re-verified for the account that pays
The re-verification of a good's saleability at payment time SHALL be unchanged by who is signed in. An account SHALL NOT be able to pay for a good that is not saleable, and no account SHALL be treated as privileged.

#### Scenario: Signing in does not make an unsaleable good payable
- **WHEN** a signed-in buyer attempts to pay for a good whose `StorefrontListing` is not `PAID_OK` or whose `GateDecision` is not publishable
- **THEN** the checkout refuses to take payment
- **AND** the refusal quotes a reason

#### Scenario: No account bypasses the gate
- **WHEN** any account, however it was registered, attempts to pay for a good that is not publishable
- **THEN** the refusal is the same one every other account receives
- **AND** no account is exempt from the gate
