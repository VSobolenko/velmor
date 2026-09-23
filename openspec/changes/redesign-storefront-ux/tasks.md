## 1. Locale foundation

- [ ] 1.1 Add `pillow` to the workspace and rebuild the lockfile; note the reason in `pyproject.toml`.
- [ ] 1.2 Storefront: add Tailwind v4 and PostCSS, move the design tokens into `@theme` in `globals.css`, keep the existing brand palette.
- [ ] 1.3 Storefront: `src/lib/i18n/{ru,be,en}.json` with every string the shop renders; `src/lib/i18n/index.ts` with `dictionaryFor(locale)`, `negotiate(acceptLanguage, cookie)`, `isLocale`.
- [ ] 1.4 Storefront: `src/proxy.ts` (the middleware file; this Next.js version names it `proxy.ts`)
      resolving `pb_locale` cookie, then `Accept-Language`, then `ru`; rewrite into `/[locale]`.
- [ ] 1.5 Storefront: move every page under `src/app/[locale]/`; `lang`, `hreflang`, localised metadata; `LanguageSwitcher` writing the cookie.
- [ ] 1.6 Storefront: `scripts/check-i18n.mjs` asserting key parity across the three files and that no component contains a literal user-facing string; wire it into `npm run lint` prerequisites.
- [ ] 1.7 Tests: negotiation order, unknown locale, dictionary parity, a locale-prefixed URL that keeps its page.

## 2. Preview imagery

- [ ] 2.1 Domain: `PreviewImage` and `LocalizedText` models; no behaviour, no validators.
- [ ] 2.2 `GoodPreview` service: published-entry check, digest-verified original (cache or origin), downscale to 1024 px long edge, WebP with JPEG fallback, derivative cached under `<delivery cache>/previews`, `Image.MAX_IMAGE_PIXELS` bounded.
- [ ] 2.3 Persistence: `catalogue_covers` table and `CatalogueCoverRepository` (`save_cover`, `by_candidate`); in-memory and Postgres implementations.
- [ ] 2.4 `GoodPreview` prefers a stored cover over the origin derivative.
- [ ] 2.5 API: `GET /catalogue/goods/{candidate_id}/preview` - 200 with `Content-Type`, `ETag`, immutable cache; 404 unpublished; 409 digest mismatch; 502 origin unreachable; no origin in any response.
- [ ] 2.6 `velmor cover set --candidate <id> --file <png> --source <codex|downloaded>` and `velmor cover list`.
- [ ] 2.7 Tests: resize bounds, media type, cache hit, digest mismatch refusal, unpublished refusal, cover preferred over origin, origin URL absent from body and headers.

## 3. Presentation and browse

- [ ] 3.1 Domain: `CataloguePresentation` (localised title and summary, category slug, source, updated_at).
- [ ] 3.2 Persistence: `catalogue_presentations` table and repository (`save`, `by_candidate`, `all`); in-memory and Postgres.
- [ ] 3.3 `PresentationService`: resolve for a locale with the ru -> source-title fallback, never at render time from a model.
- [ ] 3.4 `velmor curate`: batched model proposals for title, summary and category slug; creates missing categories through `CategoryService`; idempotent; prints a per-good report; refuses without an explicit `--apply`.
- [ ] 3.5 Catalogue query: `GET /catalogue/goods?q=&sort=&category=&license=&limit=&offset=` returning `items` and `total`; repository method with the filtering in SQL, not in Python.
- [ ] 3.6 `GET /catalogue/goods/{id}` returns the localised presentation, preview URL, licence, obligations, file size and `generated_cover` flag; still never the origin URL.
- [ ] 3.7 Tests: fallback order, search matches title and creator, sort stability, filter combinations, pagination total, DTO has no origin field.

## 4. Storefront shell

- [ ] 4.1 Local components on the token set: `Button`, `Card`, `Badge`, `Input`, `Select`, `Sheet`, `Skeleton`, `EmptyState`, `PriceTag`.
- [ ] 4.2 `SiteHeader`: logo, primary navigation, search field, language switcher, cart with item count, account; sticky; mobile drawer.
- [ ] 4.3 `SiteFooter`: brand, navigation, licence explanation, payment marks, seller disclosure link.
- [ ] 4.4 Cart state: one client store keyed by the buyer id, `aria-live` announcement on change, badge in the header.
- [ ] 4.5 Tests: build, keyboard navigation through the header, cart count updates the badge, reduced motion respected.

## 5. Home

- [ ] 5.1 Hero: one value proposition, one CTA into the catalogue, a real catalogue image rather than a stock illustration.
- [ ] 5.2 Trust strip: rights-verified, instant download, licence stated, payment marks.
- [ ] 5.3 Category tiles, at most 8 featured goods in a card grid, "view all" into the catalogue.
- [ ] 5.4 How it works: verified -> choose -> pay -> download, with the rights step first.
- [ ] 5.5 Licence explainer and FAQ (what am I buying, what may I do with it, how do I get the file, refunds).
- [ ] 5.6 Tests: empty catalogue, API unreachable, all three locales.

## 6. Catalogue

- [ ] 6.1 `ProductCard`: 4:5 media box, title, creator, licence badge, price next to the action, always-visible add-to-cart, whole card clickable, placeholder fallback.
- [ ] 6.2 Catalogue page: grid, result count, search field, sort select, category and licence filters, mobile filter sheet.
- [ ] 6.3 Pagination with a URL-carried page and locale, so a filtered view is linkable.
- [ ] 6.4 States: loading skeleton, empty result with a way out, API error.
- [ ] 6.5 Tests: filter and sort produce the URL the API receives, card renders with and without a preview, keyboard reachability.

## 7. Product page

- [ ] 7.1 Buy box above the fold: preview, title, original title, creator, price, licence badge, add-to-cart, one trust cue.
- [ ] 7.2 Details: file format and size, full licence identity, every obligation, delivery, refund rules, generated-cover label when applicable.
- [ ] 7.3 Obligations rendered as obligations (attribution text copied out), not as a comma list.
- [ ] 7.4 Related goods from the same category; CTA repeated after the details; sticky mobile CTA.
- [ ] 7.5 Tests: not-found for a withdrawn good, licence always present, obligation list complete, no origin URL in the payload.
- [ ] 7.6 Strings: this page and `AddToCartButton` take their copy from the dictionaries. `AddToCartButton` currently renders `copy.addToCart` from `src/lib/copy.ts`, so before this task is done the buy button must read the dictionary for the active locale and the file must leave `LEGACY_IMPORTERS` in `storefront/scripts/check-i18n.mjs`.

## 8. Cart, checkout, account

- [ ] 8.1 Cart page and slide-over on the new components: line items with previews, quantity stepper, remove, summary, checkout CTA.
- [ ] 8.2 Checkout: step indicator, order summary, provider selection as cards, seller disclosure block, required licence acknowledgement.
- [ ] 8.3 Return page: explicit "payment is confirmed by the provider" state, no auto-marking paid.
- [ ] 8.4 Account: order cards with status badges, order detail, entitlements with download buttons, empty states.
- [ ] 8.5 Tests: acknowledgement is required, disclosure incomplete blocks payment, order states render, download button only for active entitlements.
- [ ] 8.6 Remove the retired single-language module. `src/lib/copy.ts` holds 100 Belarusian strings and is read by 14 files, so today the cart, checkout, account and buy button render Belarusian in every locale. Every importer moves to the dictionaries, the file is deleted, `LEGACY_IMPORTERS` in `storefront/scripts/check-i18n.mjs` is emptied, and that list, its constant and its scan are deleted with it. This task is the definition of done for the change's localisation requirement.

## 9. Verification

- [ ] 9.1 `uv run ruff check`, `uv run python -m pytest packages -q`, `uv run python -m compileall -q packages velmor`.
- [ ] 9.2 Storefront `npm run build` and `npm run lint`.
- [ ] 9.3 `openspec validate --strict redesign-storefront-ux`.
- [ ] 9.4 Deploy, run `velmor curate`, and verify the catalogue is categorised.
- [ ] 9.5 Screenshots of home, catalogue, product page, cart, checkout and account at desktop and mobile width, against the live URL, quoted in the report.
- [ ] 9.6 Update `AGENTS.md` current state and the storefront skill.
