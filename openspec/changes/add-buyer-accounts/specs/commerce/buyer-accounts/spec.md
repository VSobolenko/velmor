## Purpose

Gives each buyer an account they own, so a shop visit can be attributed to one person: they register, sign in, keep a purchase history, and reach only their own orders and download rights.

## ADDED Requirements

### Requirement: A buyer can register an account
The system SHALL create an account for a buyer who supplies an email address and a password. An email address SHALL identify at most one account, compared case-insensitively and with surrounding whitespace ignored. A password SHALL have a minimum length and SHALL be refused when it is empty or shorter than that minimum.

#### Scenario: A new email address creates an account
- **WHEN** a buyer registers with an email address that no account uses and a password that meets the minimum length
- **THEN** an account is created for that email address
- **AND** the buyer is signed in without a second credential prompt

#### Scenario: An email address already in use is refused
- **WHEN** a buyer registers with an email address that an account already uses, in any letter case
- **THEN** the registration is refused with a reason
- **AND** no second account is created
- **AND** the refusal does not state whether the password was wrong, only that the address cannot be used

#### Scenario: A password below the minimum length is refused
- **WHEN** a buyer registers with a password shorter than the minimum length
- **THEN** the registration is refused with a reason naming the minimum length
- **AND** no account is created

#### Scenario: An empty email address is refused
- **WHEN** a buyer registers with an email address that is empty or consists only of whitespace
- **THEN** the registration is refused with a reason
- **AND** no account is created

### Requirement: A buyer can sign in and sign out
The system SHALL sign a buyer in when they present the email address and password of an account, and SHALL sign them out on request.

#### Scenario: Correct credentials sign the buyer in
- **WHEN** a buyer presents the email address and password of an existing account
- **THEN** they are signed in
- **AND** a session is issued

#### Scenario: A wrong password and an unknown address are refused identically
- **WHEN** a buyer presents a password that does not match the account, or an email address that no account uses
- **THEN** the sign-in is refused
- **AND** the refusal is the same in both cases, so it does not disclose which accounts exist
- **AND** no session is issued

#### Scenario: Signing out ends the session
- **WHEN** a signed-in buyer signs out
- **THEN** the session is revoked
- **AND** the credential that session used no longer grants access to anything

### Requirement: Passwords are stored only as a one-way hash
A password SHALL be stored only as a salted, one-way hash. No stored value SHALL allow the password to be recovered, and no password SHALL appear in a log, an error message, or any response.

#### Scenario: The stored value is not the password
- **WHEN** an account is created with a password
- **THEN** the value stored for that account is not the password and not reversible into it
- **AND** verifying the correct password succeeds and verifying a wrong one fails

#### Scenario: Two accounts with the same password store different values
- **WHEN** two accounts are created with the same password
- **THEN** the stored values differ

### Requirement: A session is opaque, expiring and revocable
A session credential SHALL be an opaque random value that grants access only while the session it names is valid. A session SHALL have an expiry after which it grants nothing. A session SHALL be revocable, and a revoked session SHALL grant nothing even before its expiry. The server SHALL store only a value from which the credential cannot be reconstructed.

#### Scenario: An expired session grants nothing
- **WHEN** a buyer presents a session credential whose session has passed its expiry
- **THEN** the request is refused as unauthenticated
- **AND** no account data is returned

#### Scenario: A revoked session grants nothing
- **WHEN** a session is revoked and its credential is presented afterwards
- **THEN** the request is refused as unauthenticated
- **AND** the revocation is effective immediately, without waiting for the expiry

#### Scenario: Signing in again issues a new credential
- **WHEN** a buyer signs in while already holding a session
- **THEN** a new session credential is issued

#### Scenario: A credential that was never issued grants nothing
- **WHEN** a request presents a credential that names no session
- **THEN** the request is refused as unauthenticated

### Requirement: The session credential is delivered in a hardened cookie
The session credential SHALL be delivered to the browser in a cookie that scripts on the page cannot read, that is sent only over a secure connection, and that is not sent on requests originating from another site.

#### Scenario: The cookie cannot be read by page scripts
- **WHEN** a session is issued
- **THEN** the cookie carrying it is marked as unavailable to scripts
- **AND** it is marked as sent only over a secure connection
- **AND** it is marked as not sent on cross-site requests

### Requirement: A buyer can change their password
A signed-in buyer SHALL be able to change the password of their own account by presenting the current password and a new one that meets the minimum length. Changing the password SHALL revoke the sessions that were already open, other than the one performing the change.

#### Scenario: The password is changed
- **WHEN** a signed-in buyer presents their current password and a new password meeting the minimum length
- **THEN** the new password is stored as a hash and the new password signs them in thereafter
- **AND** the old password no longer signs them in

#### Scenario: A wrong current password is refused
- **WHEN** a signed-in buyer presents a current password that does not match
- **THEN** the change is refused with a reason
- **AND** the stored password is unchanged

#### Scenario: A new password below the minimum length is refused
- **WHEN** a signed-in buyer presents a new password shorter than the minimum length
- **THEN** the change is refused with a reason
- **AND** the stored password is unchanged

#### Scenario: Changing the password closes other sessions
- **WHEN** a buyer changes their password while another session is open
- **THEN** the other session grants nothing afterwards
- **AND** the session that performed the change continues to work

### Requirement: An account can read its own profile
A signed-in buyer SHALL be able to read the email address and the display name of their own account, and SHALL NOT be able to read or change the account of another buyer.

#### Scenario: The buyer reads their own profile
- **WHEN** a signed-in buyer requests their profile
- **THEN** their email address and display name are returned
- **AND** no password value is returned

#### Scenario: The buyer cannot reach another account
- **WHEN** a signed-in buyer requests the profile of a different account
- **THEN** the request is refused
- **AND** no data about the other account is returned

### Requirement: Orders and entitlements belong to one account
Every order and every entitlement SHALL belong to exactly one account, and SHALL be readable only by that account. A request for account data without a valid session SHALL be refused, and SHALL NOT fall back to any buyer identity supplied by the caller.

#### Scenario: A buyer reads only their own orders
- **WHEN** a signed-in buyer lists their orders
- **THEN** only the orders belonging to their account are returned
- **AND** no order of another account appears

#### Scenario: Another account's order is not reachable
- **WHEN** a signed-in buyer requests an order that belongs to a different account
- **THEN** the request is refused as not found
- **AND** nothing about that order is returned

#### Scenario: A request with no valid session is refused
- **WHEN** an order list, an entitlement list, or a download is requested with no session, an expired session, or a revoked session
- **THEN** the request is refused as unauthenticated
- **AND** no buyer identity is taken from the request itself

#### Scenario: Entitlements follow the account
- **WHEN** a buyer signs in on a different browser
- **THEN** their orders and entitlements are the same ones their account holds

### Requirement: Sign-in attempts are rate limited
Repeated failed sign-in attempts against the same account or from the same origin SHALL be slowed or refused, so that a password cannot be searched at speed.

#### Scenario: Repeated failures are throttled
- **WHEN** sign-in is attempted repeatedly with wrong credentials
- **THEN** further attempts are refused or delayed rather than answered at full speed
- **AND** a correct password presented after the attempts stop is still able to sign in
