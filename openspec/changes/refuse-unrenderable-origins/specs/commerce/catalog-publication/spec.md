## ADDED Requirements

### Requirement: A good is sold only while its bytes can be shown

The catalogue SHALL contain an entry for a good only while the platform can produce a preview from
that good's origin payload. A good whose origin payload the platform cannot render SHALL be refused
at publication, with a reason that names the cause and names no origin. A catalogue entry already
published for such a good SHALL be withdrawn by the next publication pass, and the withdrawal
reason SHALL be retrievable. Nothing SHALL leave a good on sale while the shop advertises a preview
it cannot produce.

Publication SHALL decide this from the same payload it records the digest of: the digest stored on
an entry SHALL be the digest of the payload that was inspected for renderability, never a digest of
one payload and a judgement about another.

An origin that is unavailable is not a payload that cannot be rendered. This requirement does not
change what an unobtainable digest does to an entry that is already published.

#### Scenario: A payload the platform cannot render is refused with a reason

- **WHEN** publication is applied to a publishable good whose origin payload the platform cannot render
- **THEN** no catalogue entry is created for that good
- **AND** the outcome is a refusal carrying at least one reason
- **AND** the reason states the cause and contains no origin location

#### Scenario: A published good whose payload cannot be rendered is withdrawn

- **WHEN** publication is applied to a good that already has a published entry and whose origin
  payload the platform cannot render
- **THEN** that entry is withdrawn
- **AND** the withdrawal reason is retrievable and contains no origin location
- **AND** the good is no longer purchasable

#### Scenario: Re-publication of an already withdrawn good changes nothing

- **WHEN** publication is applied to a good whose entry is already withdrawn and whose origin
  payload the platform cannot render
- **THEN** the catalogue is unchanged
- **AND** the outcome states that the catalogue already matches, with a reason

#### Scenario: An origin whose payload becomes renderable is published normally

- **WHEN** a good that was refused for an unrenderable payload is presented again with an origin
  payload the platform can render
- **THEN** the good is published as an entry
- **AND** the recorded digest is the digest of the payload that was inspected

#### Scenario: Withdrawal does not retract a good already delivered

- **WHEN** a good is withdrawn because its origin payload cannot be rendered
- **THEN** no new purchase of it is possible
- **AND** an entitlement already granted by a paid order remains valid

#### Scenario: An unobtainable origin is not treated as an unrenderable payload

- **WHEN** the origin cannot be fetched at all
- **THEN** the good is refused, with a reason
- **AND** an entry already published for that good is left as it was
