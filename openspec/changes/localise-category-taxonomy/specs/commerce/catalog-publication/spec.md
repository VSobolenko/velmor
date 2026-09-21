## ADDED Requirements

### Requirement: A curated category carries a name in every served language

A curation pass SHALL propose a category name for each served language, one value per language, so
that a language the model omitted is a failure of the proposal rather than a gap discovered when a
buyer reads the shop. A proposal that does not carry a non-empty name for every served language
SHALL be refused before the category is created.

A category name is data. Nothing in this requirement permits a name to be written into a page, a
template or a component, and nothing permits a language to be chosen for the buyer.

#### Scenario: A proposal names the category in every served language

- **WHEN** a curation pass proposes a category for a good
- **THEN** the proposal carries a non-empty name for every served language
- **AND** the category is created with a name for every served language

#### Scenario: A proposal that omits a language is refused

- **WHEN** a curation pass proposes a category with no name for one of the served languages
- **THEN** the proposal is refused with a reason naming the missing language
- **AND** no category and no assignment is written

#### Scenario: An existing category keeps the names it already has

- **WHEN** a curation pass proposes a good into a category that already exists
- **THEN** the goods are assigned to that category
- **AND** the names already stored for that category are not overwritten by the new proposal

### Requirement: Curation reuses the taxonomy it already has

A curation pass SHALL be given the categories that already exist, and SHALL prefer an existing
category over a new one when the good belongs to it. A pass over a catalogue SHALL NOT produce a new
category for every good it sees.

A new category is created only when no existing category is the right one for the good, and the new
category's slug is its identity: a later pass proposing the same slug assigns to the same category
rather than creating a second one.

#### Scenario: A good that belongs to an existing category is assigned to it

- **WHEN** a curation pass proposes a category whose slug already exists
- **THEN** the good is assigned to that existing category
- **AND** no second category is created for that slug
- **AND** the report states that an existing category was reused

#### Scenario: The existing categories are available to the proposal

- **WHEN** a curation pass proposes a category for a good
- **THEN** the proposal can see the categories that already exist, with their slug and their names

#### Scenario: A good that fits no existing category creates one

- **WHEN** a curation pass proposes a category whose slug does not exist and whose slug is valid
- **THEN** that category is created with a name in every served language
- **AND** the good is assigned to it

#### Scenario: A pass over a small catalogue does not create a category per good

- **WHEN** a curation pass runs over a set of goods of kinds already represented in the catalogue
- **THEN** the number of categories grows far more slowly than the number of goods curated
- **AND** the report names, for each good, the category it was assigned to

### Requirement: A catalogue category's single stored name is not a buyer-facing value

A category SHALL have exactly one stored name for the purpose of an external catalogue node and of
ordering, and that name SHALL NOT be treated as what a buyer reads. Every buyer-facing name SHALL be
resolved for a language.

#### Scenario: The external catalogue node keeps one name

- **WHEN** a category is created or renamed
- **THEN** the external catalogue node receives exactly one name
- **AND** that does not determine the name a buyer reads

#### Scenario: Ordering does not depend on a buyer-facing name

- **WHEN** categories are listed
- **THEN** their order does not change with the language the shop is being read in
