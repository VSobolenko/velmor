## ADDED Requirements

### Requirement: A catalogue entry carries a stored presentation

The catalogue SHALL store, per catalogued good, a display title and a short summary in each
served language, together with the category the good is assigned to. The presentation SHALL
be written by an operator-run command and SHALL be editable data, not a value derived during
a page render. A modelling step may propose the values; it SHALL NOT decide them.

#### Scenario: A curation run stores what it proposed

- **WHEN** a curation run proposes a display title, a summary and a category for a catalogued good
- **THEN** those values are stored against that good
- **AND** reading the good returns them without any model or network call

#### Scenario: Curation is idempotent

- **WHEN** a curation run is executed twice with the same proposals
- **THEN** the stored presentation is unchanged and no duplicate category is created

#### Scenario: Curation cannot change what may be sold

- **WHEN** a curation run is executed
- **THEN** no good is added to or removed from the catalogue
- **AND** no `GateDecision` changes

### Requirement: Curation creates the categories it needs

A catalogued good SHALL be assignable to a category, and a category used by curation SHALL
exist as a stored category with a stable slug before the assignment is written. Assigning a
good to a category SHALL NOT change its publishability or its licence record.

#### Scenario: A proposed category is created once

- **WHEN** a curation run proposes a category slug that does not exist
- **THEN** the category is created with that slug
- **AND** later goods proposing the same slug use the existing category

#### Scenario: An uncurated good has no category

- **WHEN** a catalogued good has not been curated
- **THEN** it may have no category
- **AND** it remains catalogued, searchable and purchasable

### Requirement: The catalogue can be searched, filtered and sorted at the source

The catalogue read path SHALL answer a query with a text term, a category, a licence, a sort
order and a page, and SHALL return both the matching goods and the total number of matches.
Filtering SHALL be applied to the catalogue, never to a page of results after the fact, and a
good that is not catalogued SHALL never match.

#### Scenario: A query returns the matching goods and the total

- **WHEN** a query matches more goods than the requested page holds
- **THEN** the page holds the requested number of goods
- **AND** the total states how many matched in all

#### Scenario: A licence filter excludes the others

- **WHEN** a query filters by one licence identity
- **THEN** only goods whose record carries that licence are returned

#### Scenario: A withdrawn good is not matched

- **WHEN** a good has been withdrawn from the catalogue
- **THEN** no query returns it

### Requirement: The catalogue read model never exposes the origin location

A catalogued good's buyer-facing representation SHALL NOT contain the origin URL of the
good, its storage location, or any internal identifier beyond the good's catalogue identity.

#### Scenario: A product representation has no origin

- **WHEN** a buyer-facing catalogue or product representation is returned
- **THEN** it contains no origin URL and no internal storage path

#### Scenario: A refusal does not leak the origin

- **WHEN** a preview or delivery request is refused
- **THEN** the refusal message contains no origin URL
