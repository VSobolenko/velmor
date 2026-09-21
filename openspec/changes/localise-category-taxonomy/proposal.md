## Why

The first curation pass, over 15 goods, exposed two defects in how categories reach a buyer.

A category's name is one string for the whole shop and the curation prompt asks for it in Russian
only. The shop serves `en`, `ru` and `be` and chooses the language from the browser, so there is no
single buyer-facing language to store. On the live English home page the category tiles read
«Фотография», «Крипто-арт», «Палеонтологические образцы», and the same names appear on the category
pages and in the catalogue filter. This is the failure the storefront rebuild removed for a good's
title and summary, reintroduced one level up: the shop chose a language for the buyer.

The curation pass is never told which categories already exist, so it invents a slug for every good
it sees. Fifteen goods produced nine categories, six of them holding exactly one good, with
overlapping meanings: `historical-images` beside `historical-illustrations`, and three separate
"illustrations" categories. The prompt asks for a small set of categories but gives the model no way
to know what that set already is. A pass over the remaining 89 goods multiplies this, and a
taxonomy of one-item categories is not a way to browse.

Now is the moment because the remaining 89 goods are not curated yet. Changing this afterwards means
re-curating the whole catalogue and rewriting every category that was created wrongly.

## What Changes

- A category carries a name per served language, the same way a good's title and summary already
  do, and the buyer-facing surfaces show the name for the buyer's language.
- The curation pass proposes a category name in every served language, one field per language, so a
  missing language fails as a violation of the model's own output type instead of surfacing later as
  a silent fallback.
- The curation pass is given the categories that already exist, and is instructed to reuse an
  existing slug when the good belongs to one.
- The categories endpoint resolves a name for the requested locale, as every other catalogue
  response already does. It accepts `locale` today and drops it.
- **BREAKING** (internal, not buyer-visible): `Category` no longer treats its single `name` as the
  buyer-facing value. That single name stays, because a Saleor category node has one name and the
  repository orders by it; it becomes the operator-facing label, not what a buyer reads.

Nothing about licensing changes. This change cannot alter a verdict, cannot make a good publishable
or unpublishable, and does not touch `ENGINE_VERSION`. Category assignment is presentation and stays
presentation.

## What the buyer will see

The buyer sees a category name in the language the shop is being read in, on the three surfaces that
show one: the category tiles on the home page, the heading and title of a category page, and the
category filter on the catalogue page. No surface will show a name in a language the buyer did not
choose.

The buyer also sees a smaller, coherent set of categories, because the curator reuses the taxonomy
it already has instead of adding a category per good.

The localisation ships in this change. The strings are not new literals: the category name is data
the curation pass proposes in three languages and the API resolves for the requested locale, on the
same rule the good's title already follows. No component renders a hardcoded name.

## Capabilities

### New Capabilities

None. The behaviour changes on capabilities that already exist.

### Modified Capabilities

- `commerce/storefront`: a category name is presented in the buyer's language, on the home tiles, the
  category page and the catalogue filter.
- `commerce/catalog-publication`: a curated category carries a name in every served language, and a
  curation pass reuses the categories that already exist instead of adding one per good.

## Impact

Code:

- `packages/services/src/domain/`: `category.py`, `curation.py` (`CurationDraft`,
  `CurationProposal`), `catalogue_card.py` (`CategorySummary`), `presentation.py` (the locale enum
  and fallback rule to reuse).
- `packages/services/src/persistence/`: `schema.py`, `contract.py` (`CategoryRepository`), and both
  implementations, `postgres.py` and `memory.py`.
- `packages/services/src/commerce/`: `category_service.py`, `catalogue_service.py`
  (`category_summaries`, `category_page`), `curation.py` (the proposer port, the prompt, the
  assignment path).
- `packages/api/src/app.py`: `_category_payload` and the two category routes.
- `velmor/curate.py`: the run report.
- `storefront/`: the consumers of `CategorySummary.name` — the home tiles, the catalogue filter and
  the category page. The wire shape keeps a single `name`, already resolved for the locale, so this
  is small.

Storage: the `categories` table gains per-locale names. `PostgresStore.ensure_schema()` is
`create_all` and never alters, and the table already exists in the dev and stage databases, so the
shape is chosen to add a table rather than alter one. The Saleor name and the repository's
order-by keep working off the existing scalar column.

Systems: Saleor continues to receive one name per category node, unchanged.

Risk: the main risk is a fallback that quietly shows Russian to a buyer reading English. The design
fixes the fallback rule explicitly and the spec states it, rather than leaving the current
single-string behaviour in place as an accidental fallback.

Tests: `test_curation.py`, `test_catalogue_service.py`, `test_category_service.py`,
`test_commerce_repositories.py`, `packages/api/tests/unit/test_catalogue_browse.py`, and the
storefront suite.
