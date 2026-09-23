# Task: make the shop header one row

## Outcome

The Proofbasket header renders as ONE row at both widths, measured in the DOM on the running
site:

- at 1440x900 it is at most 80 px tall;
- at 390x844 it is at most 64 px tall.

Today it is 165 px at 1440 px wide and 217 px at 390 px wide, because its children wrap.

## Scope

Working directory: the repository root.

You may WRITE only these four files:

- `storefront/src/components/SiteHeader.tsx`
- `storefront/src/components/LanguageSwitcher.tsx`
- `storefront/src/components/MobileNav.tsx`
- `storefront/src/components/ui/Select.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. Do not touch `storefront/src/lib/i18n/**`,
`storefront/src/app/globals.css`, `ProductCard.tsx`, `AddToCartButton.tsx`, `ui/Button.tsx`,
`CartLink.tsx`, the catalogue, cart, checkout or account pages, or anything under `packages/`,
`velmor/`, `.cursor/`, `harness/`, `scripts/`, `openspec/`.

## Inputs to read first

- `AGENTS.md`
- `storefront/src/components/SiteHeader.tsx`, `LanguageSwitcher.tsx`, `MobileNav.tsx`,
  `ui/Select.tsx`, `CartLink.tsx` (read only for the last one)
- `storefront/src/app/globals.css` (read only: the token names)

## Diagnosis, already done, do not repeat it

`SiteHeader` renders `<div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-2 px-4 py-2">`.
Its children are the wordmark, a desktop-only `<nav>`, a search `<form>`, the language switcher,
the cart link and the mobile menu.

`Select` renders `<div className="flex w-full flex-col gap-1">` unconditionally. Because the
header container wraps, the language switcher takes a whole row at 100% width — measured at
1120 px wide at a 1440 px viewport — and pushes the cart onto a further row. That is the whole
defect. The measured rows are at y=8, y=60 and y=112 on desktop, and four rows on mobile.

## The pattern, from published sources, not from taste

- Desktop (>= 768 px): one row, 64-80 px tall: wordmark, primary navigation, a visible search
  field, a compact language switcher, and the cart at the far right with its count badge. The
  mobile menu button is not shown.
- Mobile (< 768 px): one row, at most 64 px tall: wordmark, a search control of at least
  44x44 px, the cart at the far right with its count badge, and the menu button. The search field
  may open on demand; the header's collapsed height must stay at or under 64 px. If keeping the
  search field visible on mobile would exceed 64 px, put it behind a toggle instead.
- The cart is always visible at the far right with the item count.
- Interactive elements are at least 44x44 px, at least 8 px apart.
- The header must not cover focused content: keep the sticky behaviour, and keep the existing
  skip link and page padding working.

Sources: customfit.ai/blog/d2c-ecommerce/ecommerce-header-design (five header functions; visible
search; cart far right with a dynamic count badge; a search control under 44x44 px is too small);
j-a-b.net/how-to-design-a-sticky-header-that-does-not-hurt-mobile-ux-or-seo/ (mobile pinned height
48-56 px, desktop 64-80 px; stacked bars kill mobile UX);
shopify.dev/docs/storefronts/themes/best-practices/performance/increase-tap-target-size (48x48 px
minimum, 8 px spacing).

## Hard rules

- `Select` must keep today's rendering for every other caller. It is used by
  `CatalogueFilters.tsx`, which passes no width. If you add a way to opt out of `w-full`, it must
  be an optional prop whose default reproduces today's output exactly, and the language switcher
  is the only caller that passes it.
- Do not change any user-facing string. Do not add a string literal. Do not edit the
  dictionaries. If you need a new string, reply `NEEDS_KEY <dictionary.key>` and stop.
- Use only the CSS custom properties already declared in `globals.css`.
- Keep the existing accessibility behaviour: the skip link, the `<nav aria-label>`, the
  `role="search"` form with its hidden label, the cart's `aria-label` and count, and the mobile
  drawer's focus trap and Escape handling. Do not remove an accessible name.
- The wordmark already renders its own anchor and accessible name; do not wrap it in a second
  link.
- No new dependency. No `TODO`. Do not run git. Nothing that reaches the network.
- **Do not ask me to confirm a design and do not end with a question.** Implement the change.
  If a decision is genuinely ambiguous, pick the option that satisfies the measurements above and
  say what you picked in your reply.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run lint
```

Do not retry a failure. If a command fails, stop and report it.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
