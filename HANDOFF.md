# Continuation brief: the Proofbasket buyer surface

This document hands the remaining work to a session that has no memory of how it got here. It records
what is true on disk and on the server, what is finished, what is open, and the facts that cost real
time to discover. Everything here was verified against the repository and the running host, not
recalled.

Read `AGENTS.md` first, then the three skills this work touches:
`.cursor/skills/run-the-project/SKILL.md`, `.cursor/skills/storefront-ux/SKILL.md`,
`.cursor/skills/rights-engine/SKILL.md`. This brief does not replace them; it tells you where the
frontier is.

Delete this file, and the one-line pointer to it in `AGENTS.md`, when the brief is closed.

## 1. Where the work stands

Repository: branch `feat/add-storefront-commerce`, HEAD `370f2233` (corrected 2026-09-24; this brief
was written against `d64c5c5` and every commit reference below was re-checked against the tree).

Deployed: the host checks out branch `deploy-74` at `/opt/velmor/app`, currently at `370f2233`.
`velmor-storefront` and `velmor-api` are both `active`.

Live shop: `https://shop.78-111-89-46.sslip.io`. Verified just now: `/en`, `/ru`, `/be`,
`/en/catalogue` all answer 200, and `/en/categories/photography` answers 200 with twelve goods.

There is one branch and one deploy branch. The host has no working GitHub remote, so code reaches it
as a git bundle (section 6).

Working end to end today: Openverse discovery, screening, the auditor graph, the gate decision,
publication, the storefront (browse, search, filters, product page, cart, checkout, account,
downloads), the print-room identity with generated imagery, three localised languages chosen by the
browser, and a curated subset of the catalogue showing category tiles.

Four OpenSpec changes are open, and all four pass `openspec validate --strict`:

| Change | Progress | Meaning |
|---|---|---|
| `redesign-storefront-ux` | 0/55 marked | The work is built and deployed; the boxes were never ticked |
| `rebrand-print-room` | 0/38 marked | Same |
| `localise-category-taxonomy` | 0/12 marked | **Built and deployed in `5f9efd4`**, which lands after the proposal commit `d64c5c5`; the boxes were never ticked either |
| `refuse-unrenderable-origins` | 12/12 marked | Built and deployed, tasks closed in `b0bdd13`; its two delta specs are still not merged, so it is a fourth change waiting on B |

Re-verified 2026-09-24 with `node scripts/harness-status.mjs`: those four, and
`openspec validate --strict --all: 11 passed, 0 failed (11 items)`. The count was three when this
brief was written; `refuse-unrenderable-origins` had been left out of it.

## 2. What remains, in order

Do them in this order. The unlettered "First" item comes before all of them and depends on nothing. A
and B are now documentation: A's implementation has already landed, so nothing in this list waits on
A. C and D are independent. E depends on A, which is satisfied - the taxonomy fix is deployed, so the
curation pass can run whenever.

### First: fix the language of the cart and checkout line titles (one Codex worker)

The prompt is written and waiting: `harness/codex/prompts/ux-cart-line-locale.md`. Nothing is
implemented. Run it as the first worker once the Codex quota resets - it is the only defect found on
the buyer surface that is not yet fixed.

A line in the cart and in the checkout shows a good's title in the language the good was **added**
in, not the language the buyer is reading. Measured on `/en/cart` at `370f2233`: the page states
`lang="en"` and its chrome is English (`Cart`, `Subtotal`, `each`, `Remove`), while its five lines
carried four Russian titles and one Belarusian, the Belarusian one added from `/be` seconds earlier.
The same good is titled `Hotel Ca' Sagredo on the Grand Canal, Venice` on `/en/goods/...`, so the
requested language's text exists and is simply not reached. Cause: `storefront/src/lib/cart.ts` stores
a `title` snapshot written at add time and never recomputed. This breaks "The shop is served in the
buyer's language"; the fallback scenario in
`openspec/changes/redesign-storefront-ux/specs/commerce/storefront/spec.md` permits a good's Russian
text only when the requested language's text is absent, which is not this case.

### A. Close `localise-category-taxonomy` rather than rebuild it

**The implementation already landed.** `5f9efd4 feat(curation): localise category names per served
language` is in this history and comes after `d64c5c5 docs(openspec): propose
localise-category-taxonomy`. This brief previously called the change "planned only, not started" and
"the only new implementation work", which was false and would have had you rebuild shipped code. Do
not rebuild it. What is open is the same shape as B: mark the twelve boxes per evidence, merge the
delta spec into `openspec/specs/`, and archive. Read `proposal.md`, `design.md`, `specs/` and
`tasks.md` in `openspec/changes/localise-category-taxonomy/` to judge it - `tasks.md` carries the
verification for each task, and these four are the ones a green suite cannot evidence, so check them
hardest:

- 4.1 and 4.2 - rendered screenshots in every language at desktop and mobile width, and `/ux-verify`.
- 5.1 and 5.2 - the curation pass over the whole catalogue, and the three-name check against the
  deployed build.

Everything else there is service-side, and `uv run python -m pytest packages -q` with
`openspec validate --strict` covers it.

Two things the change does not record, and you need both:

- The trigger was a curation pass over 15 goods that produced 9 categories, six of them holding one
  good, with names in Russian only. The live English home page shows its category tiles as
  «Фотография», «Крипто-арт», «Палеонтологические образцы». Do not re-diagnose this; the diagnosis and
  the fix are in the change.
- Read `design.md` - Decisions before writing code. Two decisions are easy to get wrong: the names go
  in a new table because `ensure_schema()` never alters an existing one (section 4), and the taxonomy
  must be read **per proposal**, not once per run, because `fill_missing` creates categories while it
  loops and a snapshot goes stale within the first two goods.

### B. Close the contract for the shipped changes

Four changes are validated but unarchived, so `openspec/specs/` is behind the code. Verified
2026-09-24: `openspec/specs/commerce/storefront/spec.md` still says only "the goods in that category
are listed",
and carries no requirement about product cards, imagery, locale routing, or designed page states. All
of those requirements exist in the delta at
`openspec/changes/redesign-storefront-ux/specs/commerce/storefront/spec.md` and have never been
merged. That is the same gap through which the shop once shipped as a list of source filenames.

The sync-and-archive step below applies to all four changes, not only the two with a ledger here.
`refuse-unrenderable-origins` carries two delta specs (`commerce/catalog-publication` and
`commerce/storefront`) and its twelve boxes are already ticked, so it needs only the merge, the
archive and a re-validation. `localise-category-taxonomy`'s ledger is in A above; both it and
`rebrand-print-room` have their own `tasks.md` verification text.

Per-change ledger so you can mark the boxes honestly instead of trusting a number. Group letters are
the task groups in each `tasks.md`.

`redesign-storefront-ux` - evidenced complete:

- 1.1 `pillow>=12.1.0` is in `pyproject.toml`. 1.2 Tailwind theme with `@theme` in
  `storefront/src/app/globals.css`. 1.3 all three dictionaries exist with 215 keys each and
  `dictionaryFor`, `negotiate`, `isLocale`. 1.5 every page sits under `src/app/[locale]/`, `lang` is
  set in `layout.tsx`, `LanguageSwitcher` writes the cookie. 1.6 `check-i18n.mjs` passes: "215 keys in
  3 locales, 69 components free of literal strings". 1.7 the storefront suite is 54 tests, all
  passing.
- 2.1-2.7 `packages/services/src/commerce/preview.py`, the `catalogue_covers` repository, the
  `/catalogue/goods/{candidate_id}/preview` route, `velmor cover set|list`, and
  `packages/api/tests/unit/test_catalogue_preview.py` all exist. Preview served as WebP from
  `/media/preview/...` was observed on the live shop.
- 3.1-3.7 `domain/presentation.py`, `commerce/presentation_service.py`, the
  `catalogue_presentations` table, `velmor curate`, and the catalogue query/endpoints all exist.
- 4.1-4.5 the component set, `SiteHeader` (it does use our `Menu`), `SiteFooter`, the cart store with
  its live region and header badge all exist.
- 5.1-5.6 `HomeHero`, `TrustStrip`, `HomeCategoryTiles`, `HomeFeaturedGoods`, `HowItWorks`,
  `LicenceFaq`.
- 6.1-6.5 `ProductCard` with a 4:5 media box, the catalogue page with search/sort/filters, URL-carried
  paging, and the loading/empty/error states.
- 7.1-7.6 `BuyBox`, `StickyBuyBar` (appears only after the buy box leaves the viewport),
  `RelatedGoods`, obligations rendered individually. 7.6 is done: `src/lib/copy.ts` is deleted and no
  file imports it.
- 8.1-8.6 cart, checkout, return and account pages; 8.6 is the same deletion as 7.6.
- 9.1-9.4 the gates have passed, the deploy is live, and a curation pass has run.

`redesign-storefront-ux` - genuinely open, and these are the reason the change cannot be archived:

- **9.5** Screenshots of home, catalogue, product page, cart, checkout and account at desktop and
  mobile width against the live URL. What exists is partial: home in `en` and `ru` at desktop and
  mobile, and one product page. The other pages and the `be` locale are not recorded.
- **9.6** Update the `AGENTS.md` current state and the storefront skill. `AGENTS.md` was corrected by
  this brief (section 7), but the storefront skill was not checked.

`redesign-storefront-ux` - drift, the code is right and the task text was wrong. This brief corrected
it; do not go looking for a `middleware.ts`:

- **1.4** named `storefront/middleware.ts`. The file is `storefront/src/proxy.ts`; the Next.js version
  in use renamed the convention.

`rebrand-print-room` - evidenced complete:

- 1.1 the token set is in `globals.css`, exposed through `@theme`. 1.3 the radius, spacing, shadow,
  font, easing and duration scales are theme values. 2.1-2.4 `Hallmark`, `HallmarkMedallion`,
  `Wordmark`, `HallmarkRule`, `HallmarkBadge` all exist with `test/brand.test.ts` covering them.
  3.1-3.7 nine Radix dependencies, every primitive wrapped under `components/ui/`, and **zero** direct
  `@radix-ui` imports outside that directory. 4.1 `Button` has the loading state the task asks for
  under the name `loading`, with `aria-busy` and a shared grid cell so the label swap cannot move the
  button. 4.3 `PriceTag` splits the amount from the currency. 4.4 the state family exists, including
  `ErrorState` and `NotFoundState`. 4.5 `Toast` with one provider-owned live region.
- 5.1-5.6 every page re-skinned, the cart and checkout included. 6.1 the four WebP assets are in
  `public/brand/generated/` and the palette was checked. 6.2 zero stock PNGs remain. 7.1-7.4
  `copy.ts` and `shop.module.css` are gone, `LEGACY_IMPORTERS` is gone from `check-i18n.mjs` along
  with its constant and its scan, and `tsc`, `lint` and the production build pass.

`rebrand-print-room` - genuinely open:

- **5.7** Render every state of every page in every locale at 390 px and 1440 px, and record the
  screenshots. Same gap as 9.5 above; do them together.
- **8.3** Run `/ux-verify` against the running shop. The command's screenshots are the evidence.
- **8.4** Run `/rights-verify` and state `ENGINE_VERSION` explicitly. This has not been run over the
  storefront work at all, and it is the check that proves the publication gate was not disturbed.

`rebrand-print-room` - drift, code right, task text wrong. This brief corrected the text of each of
these tasks so the trap is gone; do not "fix" the code back to what they used to say:

- **2.4** named `seal-soft` and `seal-strong` for `HallmarkBadge`. The shipped tokens are
  `--color-accent-soft` and `--color-accent-strong`.
- **1.2** asked for `cyrillic-ext` on both faces. Playfair Display does not offer `cyrillic-ext`, and
  requesting it fails the build; only Inter takes it. `layout.tsx` documents this.
- **4.2** named a `Field` component with an error state. There is no `Field.tsx`; the error state is an
  `error` prop on `Input` and `Textarea`, wired with `aria-invalid`, `aria-describedby` and
  `role="alert"`. The intent is met.

Then, for each of the two changes: mark the boxes per the ledger, merge the delta specs into
`openspec/specs/` following `.cursor/skills/openspec-sync-specs/SKILL.md`, archive following
`.cursor/skills/openspec-archive-change/SKILL.md`, and re-run `openspec validate --strict` on the
synced main specs. Do not mark a box you have not evidenced.

### C. Deploy and verify the live shop

Deploy with `.deploy/deploy-storefront.sh` (section 6). Then verify by looking at it: the storefront
skill's checklist, `/ux-verify`, and the screenshots that tasks 5.7 and 9.5 require. A green suite is
not evidence about a rendered page.

### D. Operational

- `LOGFIRE_TOKEN` in the host's env files is rejected (`401 Unauthorized` on every export), which
  prints a wall of warnings around every model call. Nothing is blocked. Replace the token or remove
  it deliberately.
- There is no git remote usable from the host, so nothing deployed is pushed anywhere.

### E. Curate the remaining goods

15 of 104 goods are curated. After A lands, run the pass over the rest (section 5). Do this **after**
A, not before: curating first writes Russian-only category names, and a fragmented taxonomy, onto the
whole catalogue, which is exactly what A fixes.

## 3. Honest statement of what is not known

- Closed on 2026-09-24 against the deployed `370f2233`, at 390 px: the `be` home, cart, account and
  product pages, plus `/be/no-such-page`. Every one: header 65 px with no child escaping its box,
  zero overlapping text, zero controls under 44 px, no horizontal overflow, and text in Belarusian
  ("Кошык", "У кошык", "Правы на загрузку", "Старонка не знойдзена"). The account cards are
  whole-card links at 301x44. `/be/no-such-page` answers HTTP 404 with the skip link present. The
  `be` home carries 13 images and none failed once the page was scrolled in steps.
- Still unverified, and do not read it as working: `/be` on the catalogue, a category page and the
  checkout, and every page at 1440 px in `be`. The `en` locale was measured only through the cart and
  the checkout.
- Still open: whether `/rights-verify` would pass. It has not been run over this work.
- Still open: whether the storefront skill's checklist matches the shipped surface. Not audited.
- Still open: the mobile menu and search drawer, and a completed purchase, were never driven. The
  purchase path was walked end to end in an earlier session with the stub provider; nothing was bought
  in this one.

Everything below the "Closed" line is unverified, not working.

## 4. Facts that cost time to discover

1. **`ensure_schema()` creates, and never alters.** `packages/services/src/persistence/postgres.py`
   uses `metadata.create_all`. A new table appears; a new column on an existing table does not. There
   is no `alembic.ini` and no `migrations/` directory. This is why the category-name fix adds a table.
2. **`packages/api` deliberately does not create schema.** After deploying the storefront, `/catalogue
   goods` answered 500 with `relation "catalogue_presentations" does not exist` until a schema step
   was added. `uv run velmor cover list --env dev` creates missing tables; `.deploy/deploy-storefront.sh`
   runs it.
3. **Curation needs the model credential in the API profile.** `velmor curate` loads the API profile
   (`EnvFileResolver.resolve_api`), whose `.env.dev` declares neither `OPENAI_API_KEY` nor
   `OPENAI_BASE_URL`. Without them it fails before any call with
   `UserError: Set the OPENAI_API_KEY environment variable`. Both live in
   `packages/auditor/.env.dev`. `.deploy/curate-15.sh` copies them into `packages/api/.env.dev`, which
   is gitignored. Never print or commit the values.
4. **The curation model is `openai:deepseek-chat`.** The auditor reaches it through its own
   `OPENAI_BASE_URL`. Pass the same string to `--model`. `velmor curate` refuses to run without
   `--apply`.
5. **The locale is a query parameter to the API, not a header.** `CommerceApiClient` appends
   `?locale=`. The `x-pb-locale` header exists only inside the storefront, set by
   `storefront/src/proxy.ts`. Do not add a second channel.
6. **`/catalogue/goods` caps `limit` at 60.** `limit=100` is a 422, not a short page.
7. **`size_bytes` is `number | null`, and null is not zero.** 32 of the first 50 goods have no size
   recorded. The card and the product page render the `product.sizeUnknown` dictionary string.
   Typing it `number` is what let the shop print "0 byte" on most of the catalogue; that was fixed in
   `0ee8208` and must not be reopened.
8. **`candidateId` is encoded exactly once, and where depends on the caller.**
   `CommerceApiClient.getGood` must not encode it: the `[candidateId]` route segment arrives already
   encoded (a Next.js behaviour recorded in the method's comment). A caller holding a raw id from API
   JSON must encode it with `encodeURIComponent` at the call site, as the account pages do. Getting
   this wrong 404s every product page. `storefront/test/api-client.test.ts` is the regression test and
   was proven to fail when the bug is reinstated.
9. **The lockfile must be generated with the host's npm.** The host runs npm 9.2.0; a lockfile made
   locally with npm 11 omits optional dependencies and `npm ci` then fails with
   `Missing: @emnapi/runtime ... from lock file`. Regenerate on the host with
   `npm install --package-lock-only`.
10. **`--color-muted` and `--color-line-strong` were tuned to pass WCAG.** They were changed twice to
    meet 4.5:1 for text and 3:1 for control boundaries. Do not round them back to a nicer-looking
    value; the values are in `.cursor/skills/storefront-ux/SKILL.md` and
    `.superpowers/sdd/rebrand/identity.md`.
11. **A generated image is never presented as a good's own.** `hero-printroom`, `paper-texture`,
    `plate-placeholder` and `empty-basket` each have exactly one role. A cover attached with
    `velmor cover set --source codex` must be labelled as not being the good, which the product page
    does.

## 5. Running things

```bash
uv sync
docker compose up -d
uv run velmor --help
uv run velmor sources --env dev
uv run velmor cover list --env dev          # also creates missing tables
uv run velmor curate --model openai:deepseek-chat --env dev --limit 200 --apply
uv run python -m pytest packages -q
uv run ruff check
```

Storefront:

```bash
npm --prefix storefront run lint            # includes the locale parity check
npm --prefix storefront run test:i18n
npx --prefix storefront tsc --noEmit
npm --prefix storefront run build
```

## 6. Deploying

`GITHUB_PERSONAL_ACCESS_TOKEN` is not available to the host, so `git ls-remote` there blocks on
credentials. Transfer a bundle instead:

```bash
git bundle create /tmp/velmor.bundle refs/heads/feat/add-storefront-commerce
scp /tmp/velmor.bundle root@78.111.89.46:/root/velmor.bundle
ssh root@78.111.89.46 "cd /opt/velmor/app && \
  git fetch /root/velmor.bundle 'refs/heads/feat/add-storefront-commerce:refs/heads/deploy-74' --force && \
  git checkout -f deploy-74 && git log --oneline -1"
```

Then deploy and verify:

```bash
scp .deploy/deploy-storefront.sh root@78.111.89.46:/root/ds.sh
ssh root@78.111.89.46 "bash /root/ds.sh"
```

`.deploy/deploy-storefront.sh` runs the schema step, `npm ci`, the production build, restarts
`velmor-storefront.service`, and curls the public routes. Ship scripts with `tr -d '\r'` on the host
first: a CRLF shebang fails there.

## 7. Source of truth, and the one edit this brief made

The product contract is `openspec/specs/`. The code conforms to it, not the reverse. After section B,
`commerce/storefront` and `commerce/catalog-publication` will carry the requirements the two shipped
changes introduced.

This brief corrected one statement in `AGENTS.md` that had become false: the current state described
the buyer surface as still being rebuilt, and pointed a reader at the storefront skill's
"Anti-patterns" section instead of at the shipped surface. It now describes what is deployed, and
points here.

## 8. Definition of done

- `localise-category-taxonomy` is implemented, its tasks are marked, and its boxes are evidenced.
- The same category read in `en`, `ru` and `be` shows three names and one goods count, in the home
  tiles, the catalogue filter and the category heading, on the deployed shop.
- Both shipped changes are marked, their specs are merged into `openspec/specs/`, and they are
  archived.
- `/ux-verify` and `/rights-verify` have both run, with their evidence recorded.
- Every page is rendered at desktop and mobile width in all three locales, and the screenshots are the
  evidence.
- The remaining goods are curated, and the number of categories grew far more slowly than the number
  of goods.
- `AGENTS.md` states the deployed commit and the surface it describes.
