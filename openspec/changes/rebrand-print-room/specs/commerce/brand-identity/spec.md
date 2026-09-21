# commerce/brand-identity

## ADDED Requirements

The visual identity of the buyer-facing shop: the token set, the device, the typography and the
imagery rules, stated as properties a reviewer can verify against a rendered page rather than
against an opinion.

This capability exists because a shop can be structurally correct and still be a template. It
constrains what a surface may look like, not what it does; behaviour is specified in
`commerce/storefront`.

### Requirement: One token set defines every colour a buyer sees

The shop SHALL define its colours as CSS custom properties in a single file, and SHALL expose them to the utility layer so that a utility class and a hand-written rule resolve to the same value. No component SHALL introduce a colour outside that set.

#### Scenario: A colour is not defined twice

- **WHEN** a component needs a colour
- **THEN** it uses a token, not a literal value and not a palette class that bypasses the token set

#### Scenario: Changing a token changes every surface

- **WHEN** a token's value is changed in the single definition
- **THEN** every surface using it changes, with no second definition to update

### Requirement: Text and control boundaries meet a stated contrast floor

Body text SHALL meet at least 4.5:1 against the surface it is rendered on. Large text and the boundary of an interactive control SHALL meet at least 3:1. The ratio of every pairing actually used SHALL be computed from the token values, not estimated.

#### Scenario: Secondary text is readable

- **WHEN** secondary text is rendered on any surface in the token set
- **THEN** its contrast ratio against that surface is at least 4.5:1

#### Scenario: A form control's boundary is perceivable

- **WHEN** a form control is rendered on any surface in the token set
- **THEN** the contrast ratio of its boundary against that surface is at least 3:1

#### Scenario: A decorative divider is allowed to be subtle

- **WHEN** a divider carries no meaning and delimits nothing interactive
- **THEN** it may use the lower-contrast line token
- **AND** no control boundary uses that token

### Requirement: The identity carries one device, derived from the name

The shop SHALL carry exactly one decorative device, derived from the brand name, used to mark a verified thing and to structure a page. It SHALL be rendered as vector geometry recoloured from a token, so it stays sharp at badge size and at hero size.

#### Scenario: The device marks a verified thing

- **WHEN** a surface states that a good's rights were verified
- **THEN** the device accompanies that statement

#### Scenario: There is no second motif

- **WHEN** a surface needs decoration
- **THEN** it uses the device, or it uses no decoration
- **AND** no second decorative motif or independently styled icon family is introduced

### Requirement: Typography covers every supported locale or is not used

Every typeface SHALL provide glyphs for each locale the shop serves. A typeface's coverage SHALL be verified against the font source before it is adopted, not assumed from its appearance in one script.

#### Scenario: A locale renders in the intended typeface

- **WHEN** a page is rendered in any supported locale
- **THEN** headings and body text are set in the intended typefaces
- **AND** no fallback face is substituted for a supported locale

#### Scenario: Coverage is verified before adoption

- **WHEN** a typeface is considered
- **THEN** its coverage of every supported script is established from the font source and recorded with the decision

### Requirement: Generated imagery fills a gap and never impersonates the good

A surface SHALL show the good's own imagery wherever the good has one. Generated or placeholder imagery SHALL be used only where there is nothing real to show, SHALL stay inside the token palette, and SHALL NOT be presented as the good itself.

#### Scenario: A good with a preview shows its own preview

- **WHEN** a good has a usable preview
- **THEN** the surface shows that preview
- **AND** generated imagery is not substituted for it

#### Scenario: A good without a preview gets a real placeholder

- **WHEN** a good has no usable preview
- **THEN** the surface shows a designed placeholder
- **AND** the placeholder is not presented as the good's own image

#### Scenario: An asset outside the palette is rejected

- **WHEN** a generated or placeholder asset introduces a colour outside the token set
- **THEN** it is rejected

### Requirement: Every interactive target is usable on a phone

An interactive target SHALL be at least 44 by 44 CSS pixels, SHALL be reachable without horizontal scrolling at a 390 pixel viewport, and SHALL show a visible focus indicator that meets the contrast floor against every surface it appears on.

#### Scenario: A control is reachable and perceivable

- **WHEN** a page is rendered at a 390 pixel viewport
- **THEN** every interactive target is at least 44 by 44 CSS pixels
- **AND** no content requires horizontal scrolling

#### Scenario: Focus is visible

- **WHEN** an interactive element receives keyboard focus on any surface
- **THEN** a focus indicator is visible and meets the contrast floor

### Requirement: A state a buyer can reach is designed

Every surface SHALL render a designed state for empty, loading, error and not-found, in every supported locale. A state SHALL offer a single clear next action rather than only reporting a condition.

#### Scenario: An empty result is actionable

- **WHEN** a listing has no results
- **THEN** the surface shows a designed empty state with one clear next action
- **AND** the copy is taken from the locale dictionaries

#### Scenario: A failure is explained

- **WHEN** a surface cannot load its data
- **THEN** it shows a designed error state that names what failed and offers a retry
- **AND** it does not render a raw error, a stack trace or an empty page
