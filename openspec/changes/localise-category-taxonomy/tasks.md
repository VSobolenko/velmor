## 1. Domain and storage: a name per language

- [ ] 1.1 Add a `CategoryName` value (`locale`, `name`) and give `Category` a `names` tuple, then add
      a `category_names` table keyed `(category_id, locale)` to `packages/services/src/persistence/schema.py`.
      Verify: `uv run python -m pytest packages/services/tests/unit/persistence -q` passes, including a
      new round-trip test that saves a category with three names and reads all three back by id and by
      slug. The new table is created by `ensure_schema()` on a database that already holds the old
      schema, with no `ALTER`; show that by running `uv run velmor cover list --env dev` against the
      dev database and quoting that it completes.

- [ ] 1.2 Write and read the names in both stores (`PostgresStore`, `InMemoryStore`) and update the
      `CategoryRepository` protocol, `test_commerce_repositories.py` and the
      `_IncompleteCategoryRepository` stub and `isinstance` assertions. Verify: a test proves
      `all()` returns the same order for the same data regardless of which locale is asked for, and a
      test proves listing N categories does not issue a query per category.

- [ ] 1.3 Keep the scalar `categories.name` as the external-catalogue and ordering value, and state
      that role in the model and the repository docstrings so a buyer-facing read cannot mistake it.
      Verify: tests assert the Saleor call still receives exactly one name, and that the scalar is not
      what a resolved buyer-facing name comes from when the locale differs from the fallback.

## 2. Resolution and the HTTP surface

- [ ] 2.1 Resolve a category name for a locale in `CatalogueService.category_summaries` and
      `category_page`, on the same rule as a good's title: requested locale, then the shop's fallback,
      then nothing. Verify: tests assert one category read in `en`, `ru` and `be` yields three
      different names with an identical count, that a category with no name in any language is
      omitted from the list, and that a category missing only the requested language shows the
      fallback name rather than a slug or an empty label.

- [ ] 2.2 Return the resolved name from `_category_payload` and leave the request contract as it is,
      `locale` already being a validated query parameter. Verify: `uv run python -m pytest
      packages/api -q` passes, including a test that the categories endpoint answers `en`, `ru` and
      `be` with different names, and that `?locale=de` is still a validation error.

## 3. Curation: complete names and a reused taxonomy

- [ ] 3.1 Give `CurationDraft` and `CurationProposal` one category-name field per served language and
      refuse a proposal whose name is empty for a language, naming that language. Verify: a test
      asserts a proposal omitting a language is refused with a reason that names it and writes neither
      a category nor an assignment.

- [ ] 3.2 Change the proposer port to take the categories that already exist, carry their slugs and
      names in the prompt with the instruction to reuse an existing slug, and read the taxonomy per
      proposal rather than once per run. Verify: a test asserts that a second good of a kind already
      categorised in the same run is assigned to the existing category, that no second category is
      created for that slug, and that a good fitting no existing category creates exactly one with a
      name in every served language; the prompt test asserts the existing slugs appear in the prompt
      and the origin location still does not.

## 4. The buyer surface, verified by looking at it

- [ ] 4.1 Render the three affected surfaces at desktop and mobile width in every served language and
      record the screenshots as evidence: the home category tiles, a category page, and the catalogue
      filter. Verify: for each language the category names read in that language and no other, the
      goods count per category is identical across languages, and the screenshots are attached to the
      task.

- [ ] 4.2 Run `/ux-verify` against the running shop. Verify: the command's screenshots are the
      evidence, desktop and mobile, in every locale, and a green test suite is not accepted in their
      place.

## 5. Landing

- [ ] 5.1 Run the curation pass over the whole catalogue and read the report. Verify: every good
      reports the category it was assigned to, the number of categories grows far more slowly than
      the number of goods, and no slug appears twice as a newly created category.

- [ ] 5.2 Deploy and confirm on the running shop that the same category read in `en`, `ru` and `be`
      shows three names and one goods count, in the tiles, the filter and the category heading.
      Verify: quote the three responses and the screenshots from 4.1 taken against the deployed build.

- [ ] 5.3 Run the standing gates and quote their output: `uv run ruff check`,
      `uv run python -m pytest packages -q`, `npm --prefix storefront run lint`,
      `npm --prefix storefront run build`, and `openspec validate --strict
      "localise-category-taxonomy"`.
