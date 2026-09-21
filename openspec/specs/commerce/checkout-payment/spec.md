# commerce/checkout-payment Specification

## Purpose

Takes payment for a cart and refuses to charge for anything the licence policy does not allow to be sold.

## Requirements

### Requirement: Only saleable goods can be paid for
A checkout SHALL refuse to take payment for any good whose `StorefrontListing` is not `PAID_OK`, and for any good whose most recent `GateDecision` is not publishable.

#### Scenario: A free-only good cannot be paid for
- **WHEN** a cart contains a good whose `StorefrontListing` is `FREE_ONLY`
- **THEN** the checkout refuses to take payment
- **AND** the refusal names that good and the listing that forbids the sale

#### Scenario: A good that is not publishable cannot be paid for
- **WHEN** a cart contains a good whose most recent `GateDecision` is not publishable
- **THEN** the checkout refuses to take payment
- **AND** the refusal quotes a reason from that decision

#### Scenario: A good withdrawn after being added to the cart is not charged
- **WHEN** a buyer's cart contains a good that has stopped being saleable and the buyer attempts to pay
- **THEN** the purchase is refused with a reason naming that good

### Requirement: Payment providers are interchangeable
The checkout SHALL offer more than one payment provider. Adding or removing a provider SHALL NOT change cart, order or delivery behaviour.

#### Scenario: More than one provider is offered
- **WHEN** a buyer reaches the payment step
- **THEN** more than one payment provider is offered

#### Scenario: The order is provider-independent
- **WHEN** an order is paid through any offered provider
- **THEN** the order becomes paid and the entitlement is created by the same rules

### Requirement: Card and ЕРИП payment through the Belarusian provider
The Belarusian provider SHALL support payment by bank card and by ЕРИП. A payment SHALL be treated as successful only on the provider's own confirmation, never on the buyer's return to the site.

#### Scenario: ЕРИП payment is confirmed asynchronously
- **WHEN** a buyer chooses ЕРИП and the provider later reports that payment as successful
- **THEN** the order becomes paid
- **AND** the order was not treated as paid before that confirmation

#### Scenario: Returning to the site without paying does not pay the order
- **WHEN** a buyer leaves the provider's page without paying and the provider reports no successful payment
- **THEN** the order remains unpaid
- **AND** no entitlement is created

### Requirement: Payment confirmation is idempotent
A repeated confirmation of the same payment SHALL NOT create a second paid order, a second entitlement, or a second delivery.

#### Scenario: A repeated notification changes nothing
- **WHEN** the same successful payment is confirmed more than once
- **THEN** the order is paid once
- **AND** exactly one entitlement exists for it
- **AND** its total is unchanged

### Requirement: Provider notifications are authenticated
A payment notification that cannot be authenticated as coming from the provider SHALL be refused and SHALL NOT change the state of any order.

#### Scenario: An unauthenticated notification is refused
- **WHEN** a notification arrives whose authentication is missing or invalid
- **THEN** it is refused
- **AND** no order changes state

### Requirement: Order states are observable
An order SHALL be in exactly one of the states pending, paid, failed or cancelled, and that state SHALL be visible to the buyer and to an operator.

#### Scenario: A failed payment leaves the order payable again
- **WHEN** a payment fails
- **THEN** the order is failed and grants no entitlement
- **AND** the buyer can attempt payment again

### Requirement: A refund revokes delivery
When an order is refunded, the entitlement it created SHALL be revoked and further downloads refused.

#### Scenario: A refunded order can no longer be downloaded
- **WHEN** a paid order is refunded
- **THEN** its entitlement is revoked
- **AND** a download attempt for it is refused with a reason

### Requirement: Amounts and currency are exact
The amount asked of a provider SHALL equal the sum of the order's lines, and the order's currency SHALL be passed to the provider unchanged.

#### Scenario: The charged amount matches the lines
- **WHEN** an order is created from a cart
- **THEN** its total equals the sum of its lines
- **AND** the provider is asked for exactly that amount in the order's currency
