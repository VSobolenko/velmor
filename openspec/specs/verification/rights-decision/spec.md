# verification/rights-decision Specification

## Purpose

One verification pass decides, for every candidate that has no ruling yet,
whether Velmor may publish it, and records the reason either way.

## Requirements

### Requirement: Only candidates without a ruling are verified

A pass SHALL consider only candidates that have no rights record, oldest first,
and SHALL verify at most the configured batch size in one pass.

#### Scenario: An already-ruled candidate is skipped
- **WHEN** a candidate already has a rights record
- **THEN** the pass does not verify it again

#### Scenario: The batch size bounds a pass
- **WHEN** more candidates are undecided than the configured batch size
- **THEN** the pass verifies at most the batch size and leaves the rest for a later pass

### Requirement: Evidence is recorded and its origin is distinguishable

For every candidate, the pass SHALL record the evidence its decision rests on,
and SHALL distinguish evidence obtained from the source from a reading of text by
a model. Each piece of evidence SHALL be traceable to where it was observed.

#### Scenario: A declared licence is recorded as source evidence
- **WHEN** a candidate's source reports a licence for the item
- **THEN** that licence is recorded as evidence obtained from the source

#### Scenario: A model reading is recorded as a model reading
- **WHEN** a model reads text and proposes a licence
- **THEN** the proposal is recorded as a model reading and not as source evidence

### Requirement: A model reading is never sufficient on its own

WHEN the only evidence is a model reading together with an identity match derived
from it, the pass SHALL refuse publication and SHALL state that the decision rests
only on interpretation.

#### Scenario: An interpreted identity is refused
- **WHEN** the evidence is a model reading plus an identity match derived from that reading
- **THEN** publication is refused and the refusal states that the decision rests only on interpretation

### Requirement: Investigation is bounded

A candidate whose licence cannot be resolved SHALL be investigated at most the
configured number of attempts, after which the pass SHALL stop investigating it
and SHALL either escalate it to a human or refuse it. A pass SHALL NOT investigate
a candidate indefinitely.

#### Scenario: Attempts remain
- **WHEN** a candidate's licence is unresolved and fewer than the configured attempts have been made
- **THEN** the pass investigates it and re-attempts resolution

#### Scenario: Attempts are exhausted
- **WHEN** the configured number of attempts has been reached and the licence is still unresolved
- **THEN** the pass stops investigating and the candidate is escalated or refused

### Requirement: Human review pauses a candidate, it does not decide it

WHEN confidence in an interpreted licence identity is below the configured
escalation threshold, the pass SHALL pause that candidate for a human ruling and
SHALL NOT produce a publication decision for it. The pass SHALL continue with the
remaining candidates.

#### Scenario: A low-confidence candidate is paused
- **WHEN** an interpreted identity's confidence falls below the escalation threshold
- **THEN** the candidate is paused for human review and reported as paused, with no publication decision

#### Scenario: A pause does not stop the pass
- **WHEN** one candidate is paused
- **THEN** the remaining candidates in the batch are still verified

### Requirement: Publication requires the gate's decision

A candidate SHALL be publishable only when the publication gate returns a
publishable decision, and SHALL NOT be published by any other route. Every
refusal SHALL carry at least one human-readable reason.

#### Scenario: Every condition is satisfied
- **WHEN** the gate's decision for a candidate is publishable
- **THEN** the decision carries no reasons and the candidate may be published

#### Scenario: A condition is not satisfied
- **WHEN** any condition the gate checks is not satisfied
- **THEN** the decision is not publishable and carries at least one reason

### Requirement: A candidate is ruled on once per pass

A pass SHALL record one outcome per candidate: published, refused, screened out,
or paused for human review. A candidate that has a ruling SHALL NOT be selected
for verification again in a later pass.

#### Scenario: Every candidate in the batch has an outcome
- **WHEN** a pass processes a batch of candidates
- **THEN** each candidate appears exactly once in the pass report with one outcome

#### Scenario: A ruled candidate is not revisited
- **WHEN** a later pass runs
- **THEN** candidates that already have a rights record are not verified again
