## ADDED Requirements

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
