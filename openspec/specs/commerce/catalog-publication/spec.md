# commerce/catalog-publication Specification

## Purpose

Turns a publication decision into a saleable catalogue entry, and removes that entry when the decision that justified it no longer holds.

## Requirements

### Requirement: An entry exists only while its decision is publishable and saleable
The catalogue SHALL contain an entry for a good only while that good's most recent `GateDecision` has `publishable` true and its `StorefrontListing` is `PAID_OK`. A good that is publishable but whose listing is `FREE_ONLY` SHALL be absent from the paid catalogue.

#### Scenario: A publishable good with a paid listing is listed
- **WHEN** a good's most recent `GateDecision` is publishable and its `StorefrontListing` is `PAID_OK`
- **THEN** the catalogue contains exactly one entry for that good

#### Scenario: A good that is not publishable is absent, with its reasons retained
- **WHEN** a good's most recent `GateDecision` is not publishable
- **THEN** the catalogue contains no entry for that good
- **AND** the reasons from that decision are retrievable and non-empty

#### Scenario: A publishable good whose listing is free-only is not sold
- **WHEN** a good's most recent `GateDecision` is publishable and its `StorefrontListing` is `FREE_ONLY`
- **THEN** the catalogue contains no paid entry for that good
- **AND** the recorded reason is that the listing is not `PAID_OK`

### Requirement: Publication is idempotent
Publishing the same good more than once SHALL NOT create a second catalogue entry for it.

#### Scenario: Re-publishing a good does not duplicate it
- **WHEN** a good is published twice from the same decision
- **THEN** the catalogue still contains exactly one entry for that good

### Requirement: Withdrawal follows the decision
When a good's most recent `GateDecision` stops being publishable, or its `StorefrontListing` stops being `PAID_OK`, the good SHALL be withdrawn from sale.

#### Scenario: A decision that stops being publishable withdraws the good
- **WHEN** the most recent decision for a listed good is not publishable
- **THEN** the good is no longer purchasable
- **AND** the withdrawal reason is retrievable

### Requirement: Withdrawal stops new sales without retracting delivered goods
Withdrawal SHALL prevent new purchases. It SHALL NOT, by itself, revoke an entitlement already granted by a paid order.

#### Scenario: A withdrawn good cannot be bought
- **WHEN** a buyer attempts to purchase a withdrawn good
- **THEN** the purchase is refused with a reason
- **AND** the good's existing entitlements remain valid

### Requirement: Provenance survives publication
Each catalogue entry SHALL retain an internal reference to the `RightsRecord` and `GateDecision` it was created from, including the license identity and the obligations of that record.

#### Scenario: An entry can be traced back to its decision
- **WHEN** an operator inspects a catalogue entry
- **THEN** the entry resolves to the `RightsRecord` and `GateDecision` that justified it
- **AND** the license identity and obligations of that record are available

### Requirement: Categories are managed explicitly
An operator SHALL be able to create, rename and remove a category. Removing a category that still holds entries SHALL be refused with a reason.

#### Scenario: Creating a category succeeds
- **WHEN** an operator creates a category whose name is not already in use
- **THEN** the category exists and can receive entries

#### Scenario: Removing a non-empty category is refused
- **WHEN** an operator removes a category that still contains catalogue entries
- **THEN** the removal is refused
- **AND** the refusal names the entries that block it

### Requirement: Every catalogue operation reports its outcome
An operation that adds, withdraws or reclassifies a good SHALL report whether it changed the catalogue, and when it did not, why. A silent no-op SHALL NOT be the only result.

#### Scenario: An operation that changes nothing explains itself
- **WHEN** an operation is applied to a good whose decision does not allow publication
- **THEN** the outcome states that the catalogue was not changed
- **AND** a reason is reported

### Requirement: A publication decision is derived, never asserted
A catalogue entry SHALL be created only from a decision that agrees with the gate's own ruling for
the record the decision carries. A caller that presents a decision which claims the record is
publishable while the gate's own ruling refuses it SHALL be refused with `RightsDeniedError`, and
SHALL NOT produce an entry.

Agreement is what the bridge can check. It re-derives the ruling from the decision's own record, so
it refuses a decision that contradicts the gate; it cannot attest to who built the decision.
Deriving the decision from the gate remains the caller's obligation, and this guard does not repair
the decision, does not log a warning, and is not caught into one.

A decision that is not publishable is not an error. It is an outcome the caller may present, and its
effect is unchanged: an existing entry is withdrawn or the outcome reports the refusal, carrying the
gate's reasons.

#### Scenario: A caller asserts publishable for a record the gate refuses

- **WHEN** the bridge is applied with a decision that claims `publishable` is true for a record the gate refuses
- **THEN** `RightsDeniedError` is raised
- **AND** no catalogue entry is created for that good
- **AND** no entry already present is altered

#### Scenario: A decision that is not publishable is handled as an outcome

- **WHEN** the bridge is applied with a decision that states the record is not publishable
- **THEN** the decision is handled without raising
- **AND** an existing entry is withdrawn, or the outcome reports that the catalogue already matches
- **AND** every reason the gate produced is carried on the outcome

#### Scenario: A publishable decision proceeds unchanged

- **WHEN** the gate's own ruling for a good is publishable and the caller presents it
- **THEN** the good is published or updated as before
- **AND** the recorded digest and listing are unchanged

### Requirement: A ruling recorded under a superseded engine version is reported
A `RightsRecord` carries the version of the rights engine that produced it. The publish command
SHALL compare that version with the version of the engine that is running and SHALL report a
mismatch as a reason on the outcome, so the operator sees that the ruling was not produced by the
running policy.

The comparison belongs where the outcome is reported, so a caller that applies the bridge directly
does not receive it. That is the composition root's reporting responsibility, not a property of the
bridge.

The mismatch SHALL NOT change the action taken, and SHALL NOT be silent. A refusal belongs with the
capability to decide the good again under the running engine, which is named as follow-up work and is
not part of this requirement.

#### Scenario: A ruling from an older engine is published and reported

- **WHEN** a good whose record was produced by an engine other than the running one is published
- **THEN** the action taken is the same action the ruling would otherwise produce
- **AND** the outcome carries a reason stating that the ruling came from a different engine version

#### Scenario: A ruling from the running engine carries no such reason

- **WHEN** a good whose record was produced by the running engine is published
- **THEN** the outcome carries no reason about the engine version

#### Scenario: No verdict is changed by a version bump alone

- **WHEN** the rights engine version is bumped and no verdict path is otherwise edited
- **THEN** no stored record's ruling changes
- **AND** publication of every previously publishable good still succeeds
