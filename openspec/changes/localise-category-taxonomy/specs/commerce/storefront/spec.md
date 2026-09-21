## ADDED Requirements

### Requirement: A category name is presented in the language the shop is being read in

Every surface that shows a category name SHALL show it in the buyer's language, from the same set of
served languages the shop offers and by the same resolution rule that already applies to a good's
title: if no name is stored for the requested language, the shop's fallback language is shown. A
surface SHALL NOT show a category name in a language the buyer did not choose when a name exists in
the language the buyer did choose.

The surfaces that show a category name are the category tiles on the home page, the heading and the
document title of a category page, and the category filter on the catalogue page. Category names are
data resolved for a language, not a string chosen by a component: no page MAY render a stored name
that was not resolved for the language the page is being read in.

#### Scenario: A buyer reading English sees English category names

- **WHEN** a buyer reads the shop in English and opens the home page, the catalogue page and a
  category page
- **THEN** every category name shown on those pages, in the tiles, in the filter and in the page
  heading, is English
- **AND** no category name shown to that buyer is in another language

#### Scenario: Each served language shows its own name for the same category

- **WHEN** the same category is read in each of the served languages
- **THEN** the name shown is the name stored for that language
- **AND** the set of categories, their order and their goods counts are identical across languages

#### Scenario: A language with no stored name falls back rather than showing a raw value

- **WHEN** a category has no name stored for the language a buyer is reading in
- **THEN** the name shown is the one stored for the shop's fallback language
- **AND** the buyer is not shown a slug, an identifier, an empty label or an error

#### Scenario: The category surfaces stay usable when there are no categories

- **WHEN** the shop has no categories at all
- **THEN** the home page presents the absence as an explicit empty state, with a heading and a body
  drawn from the locale dictionary
- **AND** the catalogue filter is not rendered with an empty or placeholder option
- **AND** no error is reported to the buyer

#### Scenario: A category with no name in any language is not shown under a broken label

- **WHEN** a category has no name stored in any language
- **THEN** that category is not presented on the home tiles or in the catalogue filter
- **AND** its goods remain reachable through the catalogue
- **AND** no empty or raw label is shown to the buyer
