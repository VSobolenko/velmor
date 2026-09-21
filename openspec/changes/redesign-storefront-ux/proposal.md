## Why

The commerce layer works end to end, but the surface a buyer actually sees is not a shop.
Measured on the live deployment today:

- the home page is a list of `title -> "9.99 BYN"` links. No product image, no card, no grid.
- every good in the catalogue is an image (`content_type` values: 225 `image`, 18
  `photograph`, 1 `illustration`), and not one of them is shown. The product is invisible.
- the category section renders "no categories" because no category row exists, so there is no
  way to narrow 105 goods.
- there is no search, no sort and no filter.
- the copy is Belarusian only, hardcoded, with no switcher and `<html lang="be">` fixed.
- titles are raw source filenames, up to 150 characters, in English.
- the product page is a heading, a creator line, a price and a list of obligations.

The gate did its job; the shop built on top of it does not present what the gate approved.
This change rebuilds the presentation and adds the read path it needs. The rights engine is
not touched.

### The licence concern, stated explicitly

- **Which action.** Unchanged: selling a download is `RightsAction.RESELL`, decided by the
  existing `PublicationGate`.
- **Which evidence.** Unchanged. This change reads `CatalogueEntry` rows and `RightsRecord`
  obligations; it adds no evidence path and no way to publish.
- **What the platform refuses when evidence is missing.** Unchanged. A good is visible only
  through `CatalogueEntryState.PUBLISHED`, and the preview and search paths read the same
  catalogue the gate wrote. There is no new door and no bypass.

Two consequences the design must respect, because this change adds a buyer-visible surface:

1. A preview image is derived from the origin file, so it is the first time bytes of the good
   are served before payment. The preview SHALL be a downscaled derivative served from our
   own host, SHALL pass the same digest verification as delivery, and SHALL NOT disclose the
   origin URL. Attribution obligations remain visible on the page, as CC-BY requires.
2. Curation text (a display title, a summary, a category) is produced by a model offline and
   stored as data. It is never resolved at render time and never influences a verdict.

### Effect on existing verdicts

None. `ENGINE_VERSION` does not move: no verdict can change for identical inputs, because
this change adds no evidence kind, no alias and no gate condition.

## What Changes

- **Localisation.** The storefront becomes locale-routed (`/ru`, `/be`, `/en`) with
  browser-language negotiation, a persistent switcher, localised metadata and `hreflang`.
  Russian, Belarusian and English dictionaries; no language is hardcoded into a component.
- **Product presentation.** Catalogue entries gain a stored presentation record: display
  title, short summary and category, proposed once by a model offline and editable, in all
  three languages. Titles are no longer raw source filenames.
- **Preview imagery.** A preview endpoint serves a downscaled derivative of the good from our
  own host, digest-verified and cached. Where a good has no usable image, an operator can
  attach a generated or rights-cleared cover that the same endpoint serves.
- **Browse.** The catalogue gains search, sort (price, title, recency), category and licence
  filters, and pagination.
- **A storefront that looks like a shop.** Design system on Tailwind; header with search,
  language switcher and cart; home with a hero, trust strip, category tiles and a featured
  product grid; catalogue with product cards; product page with the buy box above the fold;
  cart, checkout and account rebuilt on the same components.
- **Accessibility and mobile.** One layout system, 44 px targets, visible focus, `aria-live`
  for cart changes, reduced-motion respected.

## Capabilities

### Modified Capabilities

- `commerce/storefront`: browsing becomes a card grid with search, filters, sorting and
  pagination; the product page must carry the buy box, the file facts and the obligations
  inside the first phone viewport; and localisation, stored presentation, preview imagery,
  designed states and keyboard and phone usability become requirements of the capability
  instead of conventions nobody wrote down.
- `commerce/catalog-publication`: the catalogue gains a stored, localised presentation, an
  optional attached cover, and a queryable read path that returns the matches and the total.

Archiving `add-storefront-commerce` populated `openspec/specs/commerce/**`, so these deltas
are written against the requirements that already exist. The two a text list satisfied -
`Browsing by category` and `A product page states the licence and the attribution` - are
MODIFIED to demand what a buyer sees. Everything else is ADDED. No requirement is removed
and none contradicts the archived contract.

## Non-goals

- **No change to the rights engine.** `license_grants.py`, `license_matrix.py`,
  `publication_gate.py`, `rights_resolver.py` are not edited. `ENGINE_VERSION` does not move.
- **No new sources.** Discovery and screening are untouched.
- **No real credentials.** Payments remain in test/stub mode.
- **No checkout logic change.** Prices, providers, re-verification and grants keep their
  contracts; only the presentation of them changes.
- **No runtime model call.** Nothing in a page render calls a model. Curation is an offline
  operator command whose output is stored data.
- **No new rights decision about generated covers.** A cover is presentation. It never
  substitutes for the good, and it is labelled as a generated image on the product page.

## Impact

**Code**

- `packages/services/src/commerce/` - adds the preview service and the presentation service.
- `packages/services/src/domain/` - adds `CataloguePresentation`, `ResolvedPresentation`,
  `Locale`, `CatalogueCover`, `PreviewImage`. No existing model changes.
- `packages/services/src/persistence/` - adds two tables and their repositories.
- `packages/api/src/app.py` - the catalogue routes gain query parameters; the preview route
  is added.
- `velmor/` - `velmor curate` and `velmor cover` commands; container wiring.
- `storefront/` - rebuilt: locale routing, Tailwind design system, every page.

**Dependencies**

- New: `pillow` (preview downscaling) and `tailwindcss` under `storefront/`. Reasons and
  security notes are in `design.md`. No version moves in the existing Python dependency set.
- The preview path touches no payment, no credential and no rights code.

**Systems**

- The storefront build gains a Tailwind/PostCSS step; the deploy procedure is unchanged
  otherwise. Preview files are written under the existing delivery cache directory.

**Risk**

- Serving a pre-purchase preview is the first time origin bytes leave our host before payment.
  Mitigated by downscaling, digest verification and origin concealment, and stated here so it
  is not mistaken later for a leak.
