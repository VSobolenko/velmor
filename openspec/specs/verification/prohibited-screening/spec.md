# verification/prohibited-screening Specification

## Purpose

A candidate matching a prohibited category is refused before any rights work
happens and with a reason, so that the platform never offers content its payment
providers forbid.

## Requirements

### Requirement: A prohibited candidate is refused before rights work

WHEN a candidate matches a prohibited category, the pass SHALL refuse it, SHALL
NOT produce evidence or a rights record for it, and SHALL NOT let it reach the
publication path.

#### Scenario: A match is refused
- **WHEN** a candidate matches a prohibited category
- **THEN** it is refused and no rights record exists for it

#### Scenario: A match produces no publication decision
- **WHEN** a candidate matches a prohibited category
- **THEN** no decision on publishing it is produced, because no rights question was asked

### Requirement: Every refusal states why

Each refusal SHALL carry at least one human-readable reason naming the category
that matched, so the refusal can be explained to whoever asks why an item is
absent.

#### Scenario: A refusal names its category
- **WHEN** a candidate is refused
- **THEN** the refusal states the category it matched

### Requirement: A refusal is not neutralised by how the item is presented

A stored candidate SHALL be refused on the terms it was stored with, so a
rewritten, re-padded or re-worded listing at the source does not clear an earlier
match. The screen matches terms, not meaning: a candidate first seen only in a
language whose terms are not in the list is not caught by this screen, and the
source allowlist - not this screen - is what keeps such goods out of the funnel at
all.

#### Scenario: A reworded item is still refused
- **WHEN** the same item is listed again under a rewritten title
- **THEN** it is refused again, on the terms the pass first matched

### Requirement: Refusals are counted and reported

A pass SHALL report how many candidates it refused and for which categories. A
refusal SHALL NOT be dropped silently, and a refused candidate SHALL NOT prevent
the remaining candidates from being verified.

#### Scenario: Counts are reported
- **WHEN** a pass refuses three candidates out of ten
- **THEN** the pass reports three refusals, names the categories, and verifies the other seven

### Requirement: A clear candidate passes unchanged

WHEN a candidate matches no prohibited category, it SHALL proceed to rights
verification unmodified.

#### Scenario: No match, no interference
- **WHEN** a candidate matches no prohibited category
- **THEN** it proceeds to rights verification with its candidate data unchanged
