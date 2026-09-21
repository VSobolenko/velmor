## MODIFIED Requirements

### Requirement: Browsing by category

The storefront SHALL present the catalogue as a browsable grid of product cards. Each card SHALL state the good's title, its licence identity and its price, and SHALL show a preview image where one exists. A buyer SHALL be able to search the catalogue by text, filter it by category and by licence, sort it, and page through it. A search or filter that matches nothing SHALL be presented as empty, with a way back to the whole catalogue.

#### Scenario: A category lists its goods

- **WHEN** a buyer opens a category that contains catalogue entries
- **THEN** the goods in that category are listed as cards
- **AND** each card shows the good's title, its licence identity and its price
- **AND** each price shown is the price the checkout would charge

#### Scenario: An empty category is shown as empty

- **WHEN** a buyer opens a category that contains no entries
- **THEN** the category is presented without goods
- **AND** no error is reported to the buyer

#### Scenario: A search with no matches offers a way out

- **WHEN** a buyer's search or filter combination matches no catalogued good
- **THEN** the page states that nothing matched
- **AND** it offers a way to clear the search and the filters

#### Scenario: A filtered view is linkable

- **WHEN** a buyer sets a search term, a filter, a sort order or a page
- **THEN** those choices are carried in the address
- **AND** opening that address again reproduces the same view

#### Scenario: Only catalogued goods are searchable

- **WHEN** a good is not in the catalogue
- **THEN** it appears in no search result, in no filter and in no listing

### Requirement: A product page states the licence and the attribution

A product page SHALL display, before purchase, the license identity, every obligation recorded for the good, the file format and size of what is being bought, the delivery method, and the refund rules. The price and the purchase action SHALL be reachable inside the first viewport of a phone-sized screen, without scrolling.

#### Scenario: An attribution licence shows its attribution

- **WHEN** a good's `RightsRecord` carries attribution obligations
- **THEN** the product page shows the license identity and those obligations
- **AND** each obligation is shown as its own statement rather than as a combined label

#### Scenario: A licence with no obligations still shows its identity

- **WHEN** a good's `RightsRecord` carries no obligations
- **THEN** the product page still shows the license identity

#### Scenario: The purchase decision does not require scrolling on a phone

- **WHEN** a buyer opens a product page at a phone-sized viewport
- **THEN** the price and the purchase action are both inside the first viewport

#### Scenario: A withdrawn good has no product page

- **WHEN** a buyer requests the product page of a good that is not in the catalogue
- **THEN** the response is not found
- **AND** no price, no preview and no file is disclosed

## ADDED Requirements

### Requirement: The shop is served in the buyer's language

The storefront SHALL serve every page under a locale prefix and SHALL select the locale from the buyer's stored choice, then the buyer's stated browser preference, then Russian. The chosen locale SHALL be changeable from any page, SHALL persist for later visits, and SHALL be stated in the document's language attribute.

#### Scenario: A first visit follows the stated browser preference

- **WHEN** a buyer with no stored choice requests a page stating a preference for a served language
- **THEN** the page is served in that language
- **AND** the address carries that language's prefix

#### Scenario: An unsupported preference falls back without an error

- **WHEN** a buyer with no stored choice states a language the shop does not serve
- **THEN** the page is served in Russian
- **AND** no error is reported to the buyer

#### Scenario: A stored choice outranks the browser

- **WHEN** a buyer who previously chose a language requests a page stating a different preference
- **THEN** the page is served in the stored language

#### Scenario: Switching language keeps the buyer where they were

- **WHEN** a buyer switches language on a product page, including one with a query string
- **THEN** the same product page is shown in the new language

### Requirement: No screen carries an untranslated string

Every string a buyer reads SHALL come from the locale dictionaries. A key present in one locale and absent from another SHALL fail the storefront's own checks before deployment. No component SHALL contain a string a buyer reads.

#### Scenario: A missing translation is caught before it ships

- **WHEN** a dictionary key exists in one locale and not in another
- **THEN** the storefront check fails and names the missing key

#### Scenario: A good with no text in the requested language falls back

- **WHEN** a good has presented text in Russian only and the buyer is reading another served language
- **THEN** the Russian text is shown
- **AND** the original source title remains available on the product page

### Requirement: A good is presented by stored data, not by its source record

The catalogue SHALL present each good with a display title and a short summary taken from a stored presentation record, produced offline and editable, and never resolved by a model, a clock or a network call during a page render. Where no presentation exists, the shop SHALL present a shortened source title rather than failing.

#### Scenario: A curated good shows its display title

- **WHEN** a good has a stored presentation and a buyer opens its product page
- **THEN** the display title and the summary are shown

#### Scenario: An uncurated good still sells

- **WHEN** a good has no stored presentation
- **THEN** the catalogue shows a shortened source title
- **AND** the product page remains reachable and purchasable

#### Scenario: Presentation never decides publishability

- **WHEN** a presentation record is written for a good
- **THEN** no `GateDecision`, `RightsVerdict` or catalogue eligibility changes as a result

### Requirement: A pre-purchase preview is a derivative of the good

A catalogued good whose content is an image SHALL be shown with a preview. The preview SHALL be produced by the platform from the good's own bytes, downscaled, served from the platform's host, and obtained only from bytes that match the digest recorded at publication. The preview SHALL NOT disclose the origin location of the good. A good with no usable image SHALL be shown with a placeholder, or with an operator-attached cover that the product page states is not the good itself.

#### Scenario: A catalogued good shows a preview

- **WHEN** a buyer browses the catalogue
- **THEN** each catalogued good whose content is an image shows a preview served by the platform

#### Scenario: The origin is not disclosed by a preview

- **WHEN** any preview response is returned
- **THEN** the response body and its headers contain no origin address

#### Scenario: An unpublished good has no preview

- **WHEN** a preview is requested for a good that is not published in the catalogue
- **THEN** the response is not found
- **AND** the response does not reveal whether a record exists elsewhere

#### Scenario: Bytes that no longer match the record do not produce a preview

- **WHEN** the origin returns bytes whose digest differs from the recorded digest
- **THEN** the preview is refused
- **AND** nothing derived from those bytes is cached as a preview

#### Scenario: A cover is labelled as not being the good

- **WHEN** a good is shown with an operator-attached cover
- **THEN** the product page states that the image is not the good itself

### Requirement: Every state a buyer can reach is designed

The shop SHALL present a designed, localised state for loading, for an empty result, for a failed request, and for a good that does not exist. No such state SHALL be an unformatted error, a raw message, or a page that explains nothing.

#### Scenario: A failed request states the failure in the buyer's language

- **WHEN** the commerce API cannot be reached while a page is rendered
- **THEN** the page states that the catalogue is unavailable in the active locale
- **AND** it does not render a stack trace or an empty list

#### Scenario: An empty result offers a way out

- **WHEN** a list a buyer requested is empty
- **THEN** the page explains that and offers a next action

### Requirement: The shop is usable on a phone and with a keyboard

Every interactive control SHALL have a target of at least 44 by 44 pixels, SHALL be reachable and operable by keyboard with a visible focus indicator, and SHALL NOT depend on hover to be reachable. A change to the cart SHALL be announced to assistive technology. Motion SHALL be suppressed where the buyer asks for reduced motion.

#### Scenario: A keyboard user can buy

- **WHEN** a buyer navigates with the keyboard only
- **THEN** they can reach a good, add it to the cart and reach checkout without a pointer
- **AND** the focused control is visibly indicated at each step

#### Scenario: An action is not hover-only

- **WHEN** a page is rendered on a device without a pointer
- **THEN** every action, including adding a good to the cart, is still reachable

#### Scenario: A cart change is announced

- **WHEN** a good is added to the cart
- **THEN** the change is announced through an `aria-live` region

#### Scenario: The price carries its currency

- **WHEN** a price is displayed anywhere in the shop
- **THEN** the amount and its currency are shown together
