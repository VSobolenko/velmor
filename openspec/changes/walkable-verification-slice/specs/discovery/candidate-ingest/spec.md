## Purpose

One discovery pass turns what the enabled sources currently expose into stored
candidates, without judging rights and without hiding a source that failed.

## ADDED Requirements

### Requirement: A pass queries every enabled source

For every configured query term, the pass SHALL query each enabled source, and
SHALL NOT contact a source that is disabled.

#### Scenario: Enabled sources are queried
- **WHEN** a pass runs with two enabled sources and one configured query term
- **THEN** both enabled sources are queried for that term

#### Scenario: A disabled source is left alone
- **WHEN** a registered source is disabled
- **THEN** the pass does not query it and does not report it as queried

### Requirement: A candidate is stored once, not once per pass

A candidate already known from an earlier pass SHALL be collapsed rather than
stored a second time.

#### Scenario: The same candidate appears in two passes
- **WHEN** a source returns a candidate that a previous pass already stored
- **THEN** exactly one candidate for that item exists after the second pass

### Requirement: A broken source is reported, never silent

WHEN a source is unavailable or returns a payload the platform cannot interpret,
the pass SHALL complete, SHALL report a failure naming the source and the reason,
and SHALL NOT present that failure as a source with nothing to offer. Candidates
from the remaining sources SHALL still be stored.

#### Scenario: One of two sources is unavailable
- **WHEN** one of two enabled sources raises during a pass
- **THEN** the pass completes, the other source's candidates are stored, and the failed source is reported with a reason

#### Scenario: A payload cannot be interpreted
- **WHEN** a source returns a payload that cannot be turned into candidates
- **THEN** the pass reports that source as failed rather than as empty, and no partial candidate is stored from it

### Requirement: Discovery does not decide rights

A candidate SHALL be stored with the licence its source declares and SHALL NOT be
filtered, ranked or refused on rights grounds. A licence that the source does not
report SHALL be recorded as absent, never as a placeholder value.

#### Scenario: A non-commercial licence is still stored
- **WHEN** a source returns a candidate declaring a non-commercial licence
- **THEN** the candidate is stored and no rights decision is made about it

#### Scenario: A source declares no licence
- **WHEN** a source returns a candidate with no licence reported
- **THEN** the candidate is stored with the licence recorded as absent

### Requirement: A stored candidate is traceable to its origin

Every stored candidate SHALL record the source it came from and an address a
person can open to inspect the item, so that a later rights decision can cite
where it came from.

#### Scenario: Origin is retrievable
- **WHEN** a candidate is stored
- **THEN** the source it came from and its landing address are retrievable with it
