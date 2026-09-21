---
name: storefront-ux
description: How the buyer-facing shop is built and what it must contain - locale routing, the copy dictionaries, the design tokens, the shared components, the layout rules per page, the states, and the visual checklist. Load before creating or changing any page, component or copy under storefront/, or any buyer-facing response under packages/api/.
---

# storefront-ux

The shop is the product's face on a legal decision. The rights engine decides what
may be sold; this surface decides whether anyone buys it. It was built once as a
text list and that was a failure, so read this before touching a page.

`.cursor/rules/07-product-surface.mdc` is canonical for the policy. This skill is
the map and the procedure.

## The shape of the storefront

```
storefront/
  src/
    app/
      layout.tsx                  root: fonts, <html lang> per locale
      [locale]/
        layout.tsx                validates the locale, header + footer
        page.tsx                  home
        catalogue/page.tsx        catalogue: search, sort, filter, pagination
        categories/[slug]/page.tsx
        goods/[candidateId]/page.tsx   product page
        cart/page.tsx
        checkout/page.tsx
        checkout/return/page.tsx
        account/…                 orders, order detail, entitlements
      media/preview/[candidateId]/route.ts   proxies the API preview
    components/
      ui/                         the design system: Button, Card, Badge, Input,
                                  Select, Sheet, Skeleton, EmptyState, PriceTag
      SiteHeader.tsx  SiteFooter.tsx  LanguageSwitcher.tsx  CartProvider.tsx
      ProductCard.tsx  BuyBox.tsx  …
    lib/
      api/                        typed client for the Velmor commerce API
      i18n/                       ru.json, be.json, en.json, index.ts, paths.ts
      cart.ts
  scripts/check-i18n.mjs          key parity across locales
```

The storefront is presentation only. It holds no rights logic, no payment secret
and no privileged credential, and it never reaches the database.

## Locales

- `Locale = "ru" | "be" | "en"`, default `ru`.
- Negotiation order: the `pb_locale` cookie, then `Accept-Language` honouring `q`
  values, then `ru`. `middleware.ts` does it; a request already under a supported
  locale is left alone, and asset paths are never redirected.
- The API never negotiates. The storefront passes `?locale=` explicitly, because
  two layers guessing the language is one layer too many.
- Every internal link goes through `localePath(locale, path)`. No component builds
  a path by concatenation.
- The switcher writes the cookie and navigates to the same path under the new
  prefix, keeping the query string.

## The design system

Tokens are declared once in `src/app/globals.css` under `@theme` and are the only
place a colour, radius, shadow or spacing value is written. Names are semantic
(`--color-surface`, `--color-ink`, `--color-muted`, `--color-line`,
`--color-accent`), not literal, so a palette change is one edit.

| Component | Contract |
|---|---|
| `Button` | variants primary / secondary / ghost; sizes; loading and disabled; a stable width so a label change does not move the layout |
| `Card` | the surface primitive; the product card builds on it |
| `Badge` | the licence badge and status badges |
| `Input`, `Select`, `Textarea` | labelled, with the label wired to the control |
| `Sheet` | the mobile drawer: focus trap, Escape closes, `aria-modal` |
| `Skeleton` | the loading state of a card grid, not a spinner |
| `EmptyState` | a statement plus a way out |
| `PriceTag` | amount and currency formatted per locale, never a bare number |

## Layout rules, and where they come from

Do not re-decide these from taste. Each is from a published source, recorded here
so the research is paid for once.

| Rule | Source | Applied as |
|---|---|---|
| One value proposition and one primary CTA in the hero; no auto-rotating carousel | [Ecom Design Pro: homepage layout](https://ecomdesignpro.com/ecommerce-homepage-layout/), [Scrippt: homepage best practices](https://www.scrippt.dev/blog/ecommerce-homepage-design-best-practices-that-convert) | A static hero, one CTA into the catalogue |
| Collection tiles let a visitor self-sort; do not link the whole catalogue from the home page | same | Category tiles, and at most 8 featured goods |
| Product cards: one fixed image ratio, a dominant image, the price as the anchor near the action, one obvious action, the whole card clickable | [Ecom Design Pro: product card design](https://ecomdesignpro.com/product-card-design/) | `ProductCard`, 4:5 media box |
| Never hover-only: it punishes touch and keyboard users | same | `Add to cart` is always visible |
| Keep the buy box — title, image, price, CTA, one trust cue — inside the first mobile viewport | [Nectar: the product page layout that converts](https://www.thinknectar.com/blog/shopify-product-page-layout) | Product page: two columns on desktop, stacked with the CTA above the fold on mobile |
| Show the price next to the button; a price behind a click or below the fold loses sales | [SendOwl: designing a digital product page](https://www.sendowl.com/blog/tips-and-advice/digital-product-page-conversion-design) | Price in the buy box; the CTA repeated below the detail |
| For an intangible good the media area carries a file-type badge, a format/size/version meta row, and a licence line under the price | [CodeFronts: digital-download product card](https://codefronts.com/components/css-product-cards/digital-download-product-card/) | Format and size on the card and the product page; the licence badge on every card |
| 44 px targets, visible focus, `aria-live` for off-screen changes, a pressed / loading / success / error state on the action | [Ecom Design Pro: quick add UX](https://ecomdesignpro.com/collection-page-quick-add-ux/) | Component defaults |
| A digital good must state that the purchase is a licence, not ownership, before the transaction, disclosed separately from other terms | [Greenberg Traurig: AB 2426 licensing disclosure](https://www.gtlaw.com/en/insights/2024/12/ab-2426-new-california-law-requires-clear-licensing-disclosures-for-digital-goods) | Licence badge and obligations on the product page; a separate required acknowledgement in checkout |

The last row is a legal requirement in a jurisdiction this shop can sell into, and
it is the same principle the rights engine is built on: a buyer must know what
they are permitted to do. It is not decoration and it is not negotiable.

## Adding a page

1. Read this file and `.cursor/rules/07-product-surface.mdc`.
2. Add the copy keys to all three dictionaries first. A page with no strings ready
   is a page that will grow literals.
3. Compose from the design system. If a needed component does not exist, add it to
   `components/ui/` with its states — do not write page-local styles.
4. Design every state: loading, empty, error, not-found, unauthenticated.
5. Check the mobile layout at 390 px before the desktop layout.
6. Add the dictionary keys, then run `npm run lint` (it runs the parity check) and
   `npm run build`.
7. Update `tasks.md` evidence with a screenshot, or run `/ux-verify`.

## The visual checklist

Run this against the running shop, at 390 px and at 1440 px, in each locale.

- Does the first screen state what this is and offer one obvious next action?
- Can a buyer reach a product and add it to the cart in three interactions or fewer
  from the home page?
- Does every card show an image, a title, a licence and a price?
- Is the price on the product page visible without scrolling on mobile?
- Is the add-to-cart action visible without hover?
- Is every obligation recorded for the good shown before purchase?
- Can the language be changed from this page, and does the page stay where it was?
- Is there a designed empty state, and does it offer a way out?
- Does anything overflow, overlap or shift at 390 px?
- Is the focus ring visible on every control when tabbing?
- If the network fails, does the page say so, in the active locale?

## Anti-patterns seen in this repository

Recorded so they are not repeated.

- The catalogue as `<ul>` of `<Link>{good.title}</Link>` with a price underneath,
  while `next/image` on the same page loaded only the brand hero and the category
  tiles. The imports looked right and no good was rendered as an image.
- A product page with no image at all: title, creator, price, licence, obligations,
  add-to-cart, and nothing else.
- `copy.ts` as a single hardcoded Belarusian module imported by every component.
- `<html lang="be">` fixed in the root layout.
- `goods.slice(0, 12)` on the home page presented as the catalogue.
- A category section that rendered its "no categories" branch, because nothing ever
  created a category, and no task noticed.
- A `next/image` import used only for decorative brand art. It made the surface look
  finished while the products were invisible; a reviewer checking "does it use
  images" would have answered yes.

