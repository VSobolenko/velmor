## MODIFIED Requirements

### Requirement: Cart
A cart SHALL persist across sessions, and SHALL be preserved across signing in and signing out. A cart SHALL NOT require an account to exist, and signing in SHALL NOT discard it.

#### Scenario: A cart survives a new session
- **WHEN** a buyer adds a good to the cart and returns in a new session
- **THEN** the cart still contains that good

#### Scenario: Signing in preserves the cart
- **WHEN** a visitor with goods in the cart signs in
- **THEN** the cart still contains those goods
- **AND** checkout can continue with the same lines

#### Scenario: Signing out preserves the cart
- **WHEN** a signed-in buyer signs out
- **THEN** the goods in the cart are not discarded

### Requirement: Account and order history
Only a signed-in buyer SHALL have an account. It SHALL list that buyer's own orders and entitlements, and SHALL be able to obtain a download for any entitlement still valid. A visitor with no session SHALL be asked to sign in instead of being shown an account.

#### Scenario: A buyer sees a paid order
- **WHEN** one of a buyer's orders has been paid
- **THEN** the account lists that order as paid
- **AND** the purchased good can be downloaded from the account

#### Scenario: A buyer sees an unpaid order
- **WHEN** one of a buyer's orders has not been paid
- **THEN** the account lists it as unpaid
- **AND** no download is offered for it

#### Scenario: A visitor with no session is asked to sign in
- **WHEN** a visitor with no session opens the account
- **THEN** they are shown how to sign in
- **AND** no order, no entitlement and no download is shown

#### Scenario: The account shows only the buyer's own records
- **WHEN** a signed-in buyer has orders and another account also has orders
- **THEN** the account lists the buyer's own orders
- **AND** no order of the other account is listed

### Requirement: Checkout requires an identifiable buyer
Checkout SHALL require a buyer who is signed in. A visitor with no session SHALL be asked to sign in before payment, and SHALL NOT be able to complete a purchase by supplying an email address alone. The order created SHALL belong to the account that completed checkout.

#### Scenario: A buyer without an identifier cannot complete checkout
- **WHEN** a visitor with no session reaches payment
- **THEN** they are asked to sign in, and checkout is refused until they do
- **AND** no payment is taken

#### Scenario: Signing in returns the buyer to checkout
- **WHEN** a visitor with goods in the cart is asked to sign in at checkout and signs in
- **THEN** they return to checkout with the cart unchanged
- **AND** they can continue to payment

#### Scenario: A signed-in buyer can complete checkout
- **WHEN** a signed-in buyer reaches payment with a saleable cart
- **THEN** the order is created for that buyer's account

## ADDED Requirements

### Requirement: The shop presents signing in and registering
The shop SHALL present a sign-in page and a registration page in every supported locale, each reachable by address, each a form with a labelled field for every value it asks for, a primary action, and a link to the other page. The language a buyer reads SHALL be the locale being read, and SHALL NOT be chosen by the account.

#### Scenario: The sign-in page asks for the credentials
- **WHEN** a visitor opens the sign-in page
- **THEN** they see a labelled field for the email address and a labelled field for the password
- **AND** a primary action that signs them in
- **AND** a link to the registration page

#### Scenario: The registration page asks for the credentials
- **WHEN** a visitor opens the registration page
- **THEN** they see a labelled field for the email address and a labelled field for the password
- **AND** a primary action that creates the account
- **AND** a link to the sign-in page

#### Scenario: Both pages exist in every supported locale
- **WHEN** the shop is read in any supported locale
- **THEN** the sign-in page and the registration page are available in that locale
- **AND** every string they show comes from that locale's dictionary

#### Scenario: Submitting shows progress and refuses a second submit
- **WHEN** a visitor submits either form
- **THEN** the action shows that it is working
- **AND** the form cannot be submitted again while the first submission is in progress

#### Scenario: A refused sign-in is explained without disclosing which accounts exist
- **WHEN** a visitor submits an email address and password that do not match an account
- **THEN** the page states that the email address and password did not match
- **AND** the email address they typed is preserved
- **AND** no raw error and no internal detail is shown

#### Scenario: A refused registration names what must change
- **WHEN** a visitor submits a registration whose email address is already in use, or whose password is below the minimum length
- **THEN** the page names what must change
- **AND** the values they typed are preserved
- **AND** no raw error and no internal detail is shown

#### Scenario: The buyer's language is the locale being read
- **WHEN** a buyer whose account was created while reading one locale opens the shop in another
- **THEN** the shop is presented in the locale being read

### Requirement: The shop states whether a buyer is signed in
Every page SHALL show whether a buyer is signed in. A visitor with no session SHALL be offered an action to sign in, and SHALL NOT be offered the account. A signed-in buyer SHALL be shown their own display name and an action to sign out.

#### Scenario: A visitor with no session is offered sign-in
- **WHEN** a visitor with no session reads any page
- **THEN** the header offers an action to sign in
- **AND** it does not offer the account

#### Scenario: A signed-in buyer is shown their own name
- **WHEN** a signed-in buyer reads any page
- **THEN** the header shows that buyer's display name
- **AND** an action to sign out

#### Scenario: Signing out returns the shop to its anonymous state
- **WHEN** a signed-in buyer signs out
- **THEN** the header offers the sign-in action again
- **AND** the account is no longer reachable

### Requirement: The buyer sees and changes their own details
The shop SHALL show a signed-in buyer their own email address and display name, and SHALL offer a form to change their password that asks for the current password and the new one and states the minimum length. Neither SHALL be reachable without a session.

#### Scenario: The buyer sees their own details
- **WHEN** a signed-in buyer opens their profile
- **THEN** their email address and display name are shown
- **AND** no password value is shown

#### Scenario: The password form asks for the current password
- **WHEN** a signed-in buyer opens the password form
- **THEN** it asks for the current password and for the new one
- **AND** it states the minimum length

#### Scenario: Changing the password is confirmed
- **WHEN** a signed-in buyer changes their password successfully
- **THEN** the page states that the password was changed
- **AND** the form no longer holds the passwords that were typed

#### Scenario: A refused password change names what must change
- **WHEN** a signed-in buyer submits a wrong current password, or a new password below the minimum length
- **THEN** the page names what must change
- **AND** the stored password is unchanged

#### Scenario: Neither page is reachable without a session
- **WHEN** a visitor with no session opens the profile or the password form
- **THEN** they are asked to sign in
- **AND** no account detail is shown

### Requirement: The account states are designed for a buyer
Each page this change adds SHALL render its loading state, its error state, and its empty state where one applies. A failure to reach the service SHALL be presented as an unavailable account with a way to try again, and SHALL NOT present a raw error, a stack trace or an internal identifier.

#### Scenario: A page being loaded shows that it is loading
- **WHEN** an account page is waiting for the service
- **THEN** the page shows that it is loading
- **AND** it does not show an empty result as though the buyer had no records

#### Scenario: A failing service is presented as unavailable
- **WHEN** the account cannot be read because the service failed
- **THEN** the page states that the account is unavailable
- **AND** it offers a way to try again
- **AND** it does not show a raw error or an internal identifier

#### Scenario: A page that does not exist is presented as not found
- **WHEN** a buyer opens an account address that does not exist
- **THEN** the shop presents its not-found page
- **AND** no account detail is shown
