# Task: fix the shop shell — the header and the add-to-cart label collision

## Outcome

Two defects on the live Proofbasket storefront are gone, measured at 1440x900 and at 390x844,
in the `ru` locale:

1. The site header is ONE row: at most 80 px tall at 1440 px wide, at most 64 px tall at 390 px
   wide. Today it is 165 px and 217 px because it wraps into three and four rows.
2. No add-to-cart button anywhere prints two labels on top of each other. Today every one of
   them renders `В корзину` and `Добавлено` in the same grid cell, both `visibility: visible`,
   so the buyer sees the two strings overprinted. The same latent defect exists in the `Button`
   loading state.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/components/SiteHeader.tsx`
- `storefront/src/components/LanguageSwitcher.tsx`
- `storefront/src/components/MobileNav.tsx`
- `storefront/src/components/CartLink.tsx`
- `storefront/src/components/AddToCartButton.tsx`
- `storefront/src/components/ui/Select.tsx`
- `storefront/src/components/ui/Button.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. In particular you may NOT touch:

- `storefront/src/lib/i18n/**` (the three locale dictionaries are shared; another worker owns them)
- `storefront/src/app/globals.css` (the design tokens are WCAG-tuned; do not change a value)
- `storefront/src/components/ProductCard.tsx`, `CatalogueGrid.tsx`, the catalogue page, the
  cart/checkout/account pages (other workers own those)
- any file under `packages/`, `velmor/`, `.cursor/`, `harness/`, `scripts/`, `openspec/`
- `storefront/scripts/check-i18n.mjs`

## Inputs you must read first

- `AGENTS.md` (you read this for free; it is the project contract)
- `storefront/src/components/SiteHeader.tsx` and `storefront/src/components/ui/Select.tsx`
  (the current code)
- `storefront/src/app/globals.css` (read only: the token names you must use)
- `.cursor/skills/storefront-ux/SKILL.md` (read only: the design-system contract)

## Measured facts, do not re-diagnose

- `SiteHeader` renders `<div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-2 px-4 py-2">`.
- `Select` renders `<div className="flex w-full flex-col gap-1">` unconditionally, so the
  language switcher claims a full-width row. Measured at 1440 px: the `SELECT` is 1120 px wide,
  on its own row, and the cart is pushed onto a third row.
- Measured header height: 165 px at 1440 px wide (rows at y=8, y=60, y=112), 217 px at 390 px
  wide (rows at y=8, y=60, y=112ish, y=164).
- `AddToCartButton.tsx` lines 62-70 render both label spans in one grid cell with only
  `aria-hidden` differing. Measured: the button's `innerText` is `В корзину\nДобавлено`, both
  spans `visibility: visible`, `opacity: 1`.
- `Button.tsx` lines 84-94 have the same shape for the loading label.
- A DOM audit found 12-24 text collisions per page, on every page, in `ru`, `en` and `be`.

## The header pattern to build, and its source

This pattern is not in the storefront skill, so it is fixed here from published sources. Do not
re-decide it from taste.

- Desktop (>= 768 px): ONE row, 64-80 px tall, containing the wordmark, the primary navigation,
  a visible search field, a compact language switcher, and the cart on the far right with a
  count badge. No hamburger button on desktop.
- Mobile (< 768 px): ONE row, at most 64 px tall, containing the wordmark, a search control of
  at least 44x44 px, the cart on the right with its count badge, and the menu button. The
  search field itself may open on demand; the collapsed header must not be taller than 64 px.
- The cart is always visible at the far right and always shows the item count.
- Interactive elements: at least 44x44 px, at least 8 px apart.

Sources:
- https://www.customfit.ai/blog/d2c-ecommerce/ecommerce-header-design - five functions (brand,
  navigation, search, cart, account/trust); visible search; cart far right, always visible,
  dynamic count badge; a search control under 44x44 px is too small to tap.
- https://www.j-a-b.net/how-to-design-a-sticky-header-that-does-not-hurt-mobile-ux-or-seo/ -
  mobile pinned height 48-56 px (about 8% of the viewport), desktop 64-80 px; "stacked bars kill
  mobile UX".
- https://shopify.dev/docs/storefronts/themes/best-practices/performance/increase-tap-target-size -
  48x48 px minimum, 8 px minimum spacing.

## Hard rules

- `Select` must keep its current default for every other caller: a caller that passes nothing
  still gets a full-width control. If you add a way to opt out of the full width, it must be an
  optional prop whose default preserves today's rendering. `CatalogueFilters.tsx` uses `Select`
  and must keep working unchanged.
- Do not change the `Button` public API. `variant`, `size`, `loading`, `loadingLabel`,
  `disabled` keep their names and meaning. Fix only the visual collision: the inactive label
  must be hidden visually while still reserving the button's width, so the layout never shifts.
  `visibility: hidden` and similar are acceptable; removing the width reservation is not.
- Do not change `AddToCartButton`'s public API (`candidateId`, `title`, `unitAmount`, `currency`,
  `label`, `addedLabel`, `size`, `className`).
- Every user-facing string must come from the dictionary that is already passed in. You may not
  add a string literal. You may not edit the dictionaries. If you believe a new string is
  required, do not invent one: reply `NEEDS_KEY <dictionary.key>` and stop.
- Use only the CSS custom properties already declared in `globals.css`. Do not write a hex
  colour, a raw px radius or a raw font size where a token exists.
- No new dependency. No `try/except`-style swallow. No `TODO`.
- Do not run git. Do not run anything that reaches the network: no `npm install`, no
  `npm run build`, no `uv sync`, no `docker`.
- Keep the code style of the file you edit: TypeScript, 2-space indent, double quotes,
  explicit return types on exported functions where the file already uses them.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run lint
```

Both are local. Do not retry a failure. If a command fails, stop and report it.

## Token contract

Budget: aim to finish within a modest context. Reserve enough for the two verification commands
and the handoff. If the work cannot be done without dropping part of the scope, reply exactly
`CONTEXT_LIMIT` rather than guessing.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
