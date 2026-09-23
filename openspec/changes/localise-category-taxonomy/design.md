## Context

See `proposal.md` - Why for the defects. This section records only what constrains the approach.

- A category name is one column, `categories.name`, `Text NOT NULL`. It is written twice per row: as
  a scalar column and inside the `category` JSONB, which is what reads validate back into the model.
  The scalar exists for `ORDER BY name` in `all()` and for the Saleor category node.
- `PostgresStore.ensure_schema()` is `Schema.metadata.create_all`. Its own docstring calls itself "a
  development convenience, not a migration strategy" and states that production changes belong in
  Alembic. There is no `alembic.ini` and no `migrations/` directory in the repository, and the
  `categories` table already exists in the dev and stage databases. An `ALTER` therefore will not
  happen on deploy by itself.
- The locale precedent already exists and works for a good's title and summary:
  `catalogue_presentations` is keyed `(candidate_id, locale)` rather than candidate-with-nullable-
  columns, `PresentationService` resolves the requested locale and then the fallback locale, and
  `Locale` is a closed enum of `ru`, `be`, `en`.
- The storefront already asks for a locale: `CommerceApiClient` appends `?locale=` to every catalogue
  call, and `/catalogue/categories` already declares `locale` as a query parameter and passes it into
  `CatalogueService.category_summaries(locale)`. The service receives the locale and drops it when
  reading the name. FIX A is finishing a job the wiring already started, not new plumbing.
- Curation reads the goods, proposes copy per language, and assigns a category. `fill_missing` loops
  over entries and creates categories as it goes, so the set of existing categories changes during a
  run.

## Goals / Non-Goals

**Goals:**

- A buyer-facing category name is resolved for a language, never a stored single string.
- The curation pass reuses the taxonomy it already has and cannot propose a category name that is
  incomplete in a served language.
- The database changes without altering an existing table, so `ensure_schema()` remains sufficient
  on a machine that already has the schema.
- Ordering of categories and the Saleor category node are unaffected.

**Non-Goals:**

- Introducing a migration framework. The shape is chosen so that none is needed; a future change that
  does need one is a separate decision.
- A taxonomy model (hierarchy, tags, synonyms, merge/split operations). The fix is that curation sees
  what exists; consolidation of categories already created is the operator re-running the pass.
- Any change to the gate, the verdict path, or what may be published.
- Reworking how a good's own copy is localised. That already works.

## Decisions

**Names live in a new `category_names` table, keyed `(category_id, locale)`, mirroring
`catalogue_presentations`.**

Alternatives and why they lose:

- *Three nullable columns on `categories`* (`name_ru`, `name_be`, `name_en`): requires an `ALTER` on
  an existing table, which neither `ensure_schema()` nor any tooling in this repository performs. It
  also contradicts the reason the presentation contract gives for the row-per-locale shape. It would
  need a migration for every language the shop adds.
- *A `names` map inside the existing `category` JSONB*: needs no DDL, which is attractive, but it
  makes the validated model carry a field that is absent in every existing row. That forces either a
  default, which the project forbids for making missing data quiet, or conditional validation, which
  puts a branch in the domain model to work around storage. It also hides the names from any query
  that would want to select them.
- *One name, translated at render time by the storefront*: impossible in general. The slugs are
  proposed by a model, so a component cannot hold a dictionary for them, and inventing one is the
  hardcoded-language failure the product-surface rule forbids.

`Category` gains `names: tuple[CategoryName, ...]`; `CategoryName` is `(locale, name)`. The repository
reads and writes the names with the category. Listing categories must fetch the names in one query
for the whole list, not one per category.

**The scalar `categories.name` stays, with a role that is explicitly not buyer-facing.**

It remains what a Saleor category node is given and what `all()` orders by, so neither the external
catalogue nor the category order depends on the language a buyer reads. The Russian buyer-facing name
is stored in `category_names` like the other two; the scalar is not read for a buyer-facing surface
without going through resolution. The cost is two places that hold something called a name, which is
a real risk and is called out below.

**Resolution is requested locale, then the shop's fallback locale, then nothing.**

The same rule `PresentationService` already applies, so the shop has one fallback policy rather than
two. A category with no name in any language is not presented on the tiles or in the filter, and its
goods stay reachable through the catalogue. The fallback is a safety net, not the mechanism: curation
refuses a proposal that omits a served language, so a category created by a curation pass always has
all three.

*Alternative considered:* refuse to render a category whose requested-locale name is missing, the
way the gate refuses an unproven licence. Rejected, and the difference matters: the gate protects a
legal position, where refusing is the safe answer. A missing translation is a gap in presentation,
and hiding a category a buyer can legitimately buy is a worse outcome than showing its name in the
fallback language.

**The proposal port takes the existing categories as an argument, not as constructor state.**

`CurationProposer.propose(candidate, existing)` where `existing` is the categories read at that
moment. The alternative, reading the taxonomy once when the service is built, is wrong for a reason
that is easy to miss: `fill_missing` creates categories while it loops, so a taxonomy captured once
would be stale by the second good, and a pass would create duplicates of the categories it created
earlier in the same run. Re-reading per proposal is what makes the reuse rule hold for the run and
not only across runs.

The prompt carries each existing category's slug and its names, and the instruction to reuse an
existing slug when the good belongs to it. Nothing about the model's authority changes: the slug it
returns is validated, the assignment is presentation, and no value here can make a good publishable.

**Curation proposes one name field per served language.**

`CurationDraft` gains `category_name_ru/be/en`, one field each, for the same reason its title and
summary fields are one per language: an omitted language becomes a violation of the model's own
output type instead of a gap found later by a buyer. `CurationProposal` carries the same three
values, and `_require_storable` refuses an empty one, naming the language.

**Which name the Saleor node receives: the Russian one.**

Consistent with `_product_name`, which already uses the `ru` title as the Saleor product name. Saleor
is the external catalogue, not what the storefront reads to show a name.

**The already-curated categories are fixed by re-running curation, not by a data patch.**

The 15 curated goods produced 9 categories with Russian names in the scalar only. After this change
those categories have no `category_names` rows, and the spec fixes what that means: a category with
no name in any served language is not presented on the home tiles or in the filter, so those 9 are
hidden rather than shown in a fallback language.

A pass therefore has to reach them, and a good whose presentation is already complete must not be
skipped while its category is still nameless. ``fill_missing`` treats "this good needs no copy **and**
its category is named in every served language" as the condition to walk past; otherwise it proposes
for the good, which writes no copy because ``_store`` fills only the locales the good is missing, and
writes the category's absent names. That is what makes the migration reach the 9 without a data
patch: the same pass, over the whole catalogue, that fixes the fragmented taxonomy.

The migration is the operator pass over the whole catalogue. This is why the change is worth landing
before curating the remaining goods rather than after.

## Risks / Trade-offs

- *Two things called a name exist, and a later change reads the wrong one* -> The buyer-facing read
  goes through one resolution point, and a test asserts that a resolved name is never equal to the
  scalar when the locale differs from the fallback. The role of the scalar is stated in the model and
  in the repository docstring.
- *The 9 existing categories are hidden during the window before the pass* -> Known and accepted for
  the interval between the deploy and the pass; the mitigation is that landing this change and running
  the pass are one operation, and the pass reaches those categories because a good whose category is
  nameless is proposed for rather than skipped. The alternative - falling back to the scalar name -
  is what the spec forbids, because it shows a buyer a language they did not choose.
- *A category name is written onto an existing category* -> The names that are already stored are
  never overwritten; a proposal fills only the served languages the category is missing. A spec
  scenario asserts this, and the pass is idempotent because a fully named category is not proposed for.
- *Listing categories costs one query per category* -> The names are fetched for the whole list in one
  query. A test over a multi-category catalogue asserts the read count does not grow with the number
  of categories.
- *The slug is model-proposed, so two passing runs can still disagree and create near-duplicates* ->
  Reduced, not eliminated. Seeing the existing taxonomy is what makes reuse the model's default, and
  a slug that already exists is never duplicated. Genuine consolidation stays an operator decision.
- *Existing tests assert a single `category.name`* -> They are updated in the same change; a test that
  still asserts the single name is a test asserting the defect.

## Migration Plan

1. Deploy. `ensure_schema()` creates `category_names`; no existing table is altered. A category with
   no rows in the new table has no buyer-facing name in any language, so it is not presented on the
   home tiles or in the filter and its page reads as not found - which is why the pass in step 2 runs
   in the same operation rather than later. The catalogue itself is unaffected: every good stays
   browsable, searchable and purchasable.
2. Run the curation pass over the catalogue. It writes names for every served language and reuses
   slugs, which also consolidates the fragmented categories.
3. Verify on the running shop: the same category read in `en`, `ru` and `be` shows three names and an
   identical goods count, in the tiles, the filter and the category heading.

Rollback: reverting the code leaves `category_names` in place, unread. No data is lost and no other
table was changed. The scalar name is still there, so the previous behaviour is recoverable without
a data migration.

## Open Questions

- Whether the operator-facing surface should show all stored names for a category, or only the scalar
  label. Deferrable: it changes no spec and no task, and the scalar is a correct operator label today.
