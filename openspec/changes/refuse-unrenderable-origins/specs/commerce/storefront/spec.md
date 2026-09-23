## ADDED Requirements

### Requirement: A preview refusal is distinguishable from a good that is absent

The preview endpoint SHALL answer not found only when no saleable good exists at that address: a
good that is unknown, a good that has been withdrawn, or a good whose listing is not `PAID_OK`. A
good that exists and is saleable but whose origin payload the platform cannot render SHALL be
reported as a preview that could not be produced, and SHALL NOT be reported as a good that is
absent.

No response, header or refusal SHALL contain any part of the origin location, and no refusal SHALL
describe a property of the payload, such as its format, its media type or its size.

What the buyer sees is the same either way: a page showing a good whose preview is refused shows
the shop's own placeholder image, never a broken tile, never an empty box and never a line of text
in the image's place.

#### Scenario: A good that is not saleable is answered as absent

- **WHEN** a preview is requested for a good that is unknown, withdrawn or not `PAID_OK`
- **THEN** the response is not found
- **AND** the response body contains no origin location

#### Scenario: A saleable good whose payload cannot be rendered is not reported as absent

- **WHEN** a preview is requested for a saleable good whose origin payload the platform cannot render
- **THEN** the response says that the preview could not be produced
- **AND** it is distinguishable by its response status from a good that is not saleable
- **AND** the response body contains no origin location and describes no property of the payload

#### Scenario: The buyer sees the placeholder either way

- **WHEN** a buyer opens a page showing a good whose preview is refused
- **THEN** the page shows the shop's own placeholder image in the place of the preview
- **AND** it shows no broken tile, no empty box and no line of text in that place
- **AND** the good's own title remains the accessible name of that image

#### Scenario: The refusal is legible to an operator without telling a buyer anything

- **WHEN** any preview is refused
- **THEN** an operator can tell a withdrawn good from a payload the platform cannot render
- **AND** a buyer cannot learn from the response whether the good exists, where it came from, or
  what its payload is
