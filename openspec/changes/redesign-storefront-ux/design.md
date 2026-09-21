## Context

`add-storefront-commerce` built the commerce path and a Next.js presentation layer over it.
The commerce path is correct and stays. The presentation layer was built to prove the path,
not to sell: it renders text lists in one hardcoded language.

This design covers the presentation rebuild plus the two read-path additions it needs: a
stored, localised presentation per good, and a downscaled preview image.

## Layer placement

| Piece | Layer | Why |
|---|---|---|
| `CataloguePresentation`, `LocalizedText`, `PreviewImage` | `packages/services/src/domain/` | Plain typed data, no behaviour, no imports. |
| `PresentationService` | `packages/services/src/commerce/` | Domain logic over repositories; must not import an agent, a framework or the storefront. |
| `GoodPreview` | `packages/services/src/commerce/` | Same layer as `DeliveryService`, whose digest check and cache it reuses. |
| Persistence (two tables, two repositories) | `packages/services/src/persistence/` | Follows the existing repository pattern; nothing here decides publishability. |
| Routes | `packages/api/` | The HTTP surface; it maps a service result to a response and decides nothing. |
| `velmor curate`, `velmor cover` | `velmor/` (composition root) | Operator commands that choose concrete classes; the only place that may. |
| Every page, component and string | `storefront/` | The scoped Node exception. No rights logic, no payment secret, no privileged credential. |

The dependency direction is unchanged: `storefront` -> HTTP -> `packages/api` ->
`packages/services` -> `packages/core`. The storefront imports nothing from Python and reads
no database.

## Decisions

**D1 - Locale routing is `/<locale>/...`, negotiated by middleware.**
A path segment, not a cookie-only switch, so a locale is linkable, indexable and cacheable,
and so a shared URL keeps its language. `middleware.ts` resolves the locale in this order:
the `pb_locale` cookie, then `Accept-Language`, then `ru`. The switcher writes the cookie and
navigates to the same path under the new prefix. Rejected: a client-side dictionary provider
(no per-locale URL, worse for sharing and for a first paint that is already localised).

**D2 - Copy is data, not code.** `src/lib/i18n/{ru,be,en}.json`, one flat file per locale,
loaded by the server component tree. A key missing in one locale is a build failure, checked
by `storefront/scripts/check-i18n.mjs` (Node's built-in modules only, no test dependency).
Rejected: inline ternary strings, which is what produced the current single-language surface.

**D3 - A good's presentation is stored data, written offline.** A model proposes a display
title, a short summary and a category slug; `velmor curate` writes them as rows. Render is a
database read with no model, no clock and no randomness. A locale with no text falls back to
the Russian text, and the raw source title is kept and shown as "original title" on the
product page so provenance is not hidden.

**D4 - Preview is a downscaled derivative, served by us, digest-verified.**
`GET /catalogue/goods/{candidate_id}/preview`:
1. refuse unless the entry exists and is `PUBLISHED`;
2. take the original from the delivery cache by digest, or fetch `origin_url` and require
   `sha256(body) == entry.content_digest` (the delivery rule, unchanged);
3. downscale to at most 1024 px on the long edge and encode WebP (JPEG fallback);
4. cache the derivative under the existing delivery cache root, in a `previews` subdirectory,
   keyed by digest and width;
5. respond with an immutable `Cache-Control` and an `ETag` derived from the digest.

The origin URL is never in the response, an error body or a header. Only a `PUBLISHED` entry
has a preview, so the endpoint cannot become a way to read a refused good.

Failure modes considered: origin unreachable (502, no derivative cached), origin no longer
matches the digest (409, the delivery rule), payload not decodable as an image (404, the
storefront falls back to its own placeholder), derivative larger than the cache budget (not
cached, still served). The design accepts a cold first request per good; a warm cache is the
normal case.

**D5 - A generated cover is stored data, never a runtime generation.**
Where a good has no usable image, an operator attaches a cover (`velmor cover set --file`).
Generated covers come from the Codex `image_gen` tool, which is the only image generator
wired up in this repository and has no network access; anything fetched instead is fetched by
us and must carry a recorded licence. The cover is stored with its source, served by the same
preview endpoint, and labelled on the product page as not being the good itself. Nothing in
a render path calls a model or the network.

**D6 - Tailwind, one token set, components owned by us.**
Tailwind v4 with the design tokens in `globals.css` (`@theme`), plus a small set of local
components (`Button`, `Card`, `Badge`, `Input`, `Select`, `Sheet`, `Skeleton`, `EmptyState`).
No component library is vendored in: the pages are ours and the component count is small.
Rejected: keeping hand-written CSS modules, which is what the current inconsistent surface is
made of; and pulling in a full UI kit, which brings a second design language and a larger
dependency surface than the shop needs.

**D7 - The shop is laid out from the research, not from taste.** The concrete rules this
design implements, each traceable to a published source:

| Rule | Applied as |
|---|---|
| One value proposition, one primary CTA in the hero; no auto-rotating carousel | Static hero, one CTA into the catalogue |
| Collection tiles so a visitor self-sorts instead of seeing the whole catalogue | Category tiles above the product grid, at most 8 goods featured |
| Product cards: consistent image ratio, title, price as the anchor, one obvious action, whole card clickable, action not hover-only | `ProductCard` with a 4:5 media box, price next to the action, `Add to cart` always visible |
| Buy box (title, image, price, CTA, one trust cue) inside the first mobile viewport | Product page: two columns on desktop, stacked with the CTA above the fold on mobile |
| Price visible without a click; CTA repeated after the detail sections | Price in the hero of the product page; CTA repeated below the details |
| Licence and permitted use stated before purchase; a separate acknowledgement at checkout | Licence badge and obligations on the product page; a licence checkbox in checkout |
| 44 px touch targets, visible focus, `aria-live` on cart changes, reduced motion respected | Component-level defaults |

**D8 - Search, sort and filter are server-side.** `GET /catalogue/goods` gains `q`, `sort`,
`category`, `license`, `limit`, `offset` and returns a total. Filtering in the browser over a
105-item catalogue would work today and stop working at a larger size; the repository query is
where the catalogue's size is known.

## New dependencies

| Dependency | Reason | Security note |
|---|---|---|
| `pillow` (Python) | Decode and downscale the origin image so a catalogue page does not ship multi-megabyte files. Measured: the goods average 2.5 MB, the largest is 16.6 MB. | The only parser of untrusted bytes this change adds. It runs on our server over files we already fetch and hash for delivery. `Image.MAX_IMAGE_PIXELS` is set to bound decompression bombs, and decode failure is a refusal, not a fallback. No format that can execute is enabled for output; output is WebP/JPEG only. |
| `tailwindcss` + `@tailwindcss/postcss` (storefront) | One design token set and one layout system across the rebuilt surface, which is what the current inconsistency is missing. | Build-time only. It ships no runtime code to the browser and touches no secret. The storefront still holds no payment secret and no privileged credential. |

## What is deliberately not done

- **No per-good pricing.** The flat `CATALOGUE_UNIT_AMOUNT` stays; the price anchor on the
  card is that value. Per-good pricing needs a pricing decision, not a layout change.
- **No reviews or ratings.** The research recommends them; there is no review data, and
  inventing ratings would be a lie on a page that sells legal licences.
- **No customer accounts beyond the buyer id.** Real authentication is a separate change; the
  header shows the account entry the API already supports.
- **No automatic category curation on a schedule.** `velmor curate` is run by an operator.
- **No image generation inside the product.** Codex generation is an offline operator step.
- **No dark theme.** The research mentions it; it doubles the visual surface that must be
  reviewed and is not what was asked for.

## Failure modes

| Failure | Behaviour |
|---|---|
| Curation never run | Cards fall back to a trimmed source title, categories are empty, and the catalogue still browses and sells. No page breaks. |
| Preview origin unreachable | The card shows the placeholder; the product page still sells. |
| Origin no longer matches the recorded digest | Preview refuses; delivery already refuses. Same rule, one place. |
| Translation missing for a key | Build fails (D2). Missing for a good (no be text) | Falls back to Russian, then to the source title. |
| Storefront API unreachable | The page renders an explicit error state in the active locale, not a stack trace or an empty list. |

## Risks

- **Pre-purchase bytes.** Mitigated by downscaling and digest verification (D4); stated in the
  proposal so it is a recorded decision rather than an accident.
- **Curation cost.** One batched model run over the catalogue. It is an operator command, not
  a scheduled job, and its output is stored so it is paid for once.
- **A visual rebuild is judged visually.** Verification is a screenshot set of every page at
  desktop and mobile width against the live deployment, quoted in the report, not a claim.
