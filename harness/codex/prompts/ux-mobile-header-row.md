# Task: make the shop header contain its own contents at every width

## Outcome

On the running storefront, at viewport widths 320, 360, 390, 768, 1024 and 1440 CSS pixels:

1. the `header` element is at most 64 px tall and lays its contents out in ONE row;
2. every child of the header's inner row is fully inside the header's box - none has
   `top < header.top - 1` and none has `bottom > header.bottom + 1`;
3. `document.documentElement.scrollWidth <= window.innerWidth` - no horizontal overflow;
4. every visible interactive control in the header is at least 44x44 px with at least 8 px
   between neighbours.

## Measured defect - already diagnosed, do not re-investigate

Measured in the DOM on the deployed site at a 390x844 viewport:

- `header` is `375x65`; its inner row is `display:flex`, `flex-wrap:nowrap`, height `64px`.
- Row children and their widths: wordmark anchor `120.4`, cart `div.ml-auto.lg:ml-0` `117.3`,
  mobile cluster `div.lg:hidden` `89.3`; plus `gap-2` (8 px) twice and `px-4` (32 px). The
  natural widths sum to `381.4`, against `375` available.
- The mobile cluster is `display:block` and holds two `inline-flex` buttons of `44px`, the
  first carrying `mr-2`. Its natural content width is `96px`. Because the row was short of
  space, the flex algorithm shrank the cluster to `89.3px`, the two inline buttons wrapped
  onto separate lines, and the cluster became `89px` tall inside the `64px` row: it overflows
  `12.5px` above the viewport top and `11.5px` below the header's bottom edge.
- At `320px` the cluster is squeezed to `59.5px` and is still `89px` tall. The defect is worse
  the narrower the viewport.

Root cause: a `block` container of `inline-flex` children is compressible, and its children
wrap when it is compressed. A single `flex-nowrap` row whose items can be shrunk below their
content width cannot guarantee one line.

## Required direction

- The mobile control cluster must be a single non-wrapping row that cannot be compressed below
  its content width.
- The header must fit at 320 px. Three 44 px controls plus a 120 px wordmark plus the cart does
  not fit there: pick the smallest set of changes that makes it fit and state what you picked.
  Two acceptable mechanisms, in order of preference:
  1. make the cart compact below `sm` (the count badge stays, the accessible name is
     preserved, and the visible text label may be dropped below `sm`); and/or
  2. reduce the wordmark's rendered size below `sm`.
  Do not delete the cart, the search or the menu from the mobile header, and do not let the
  wordmark's text become truncated or overlap.
- Below `lg` the search stays reachable; it may remain a toggle that opens a field, as it does
  today. If, and only if, no arrangement with three visible controls fits 320 px, move the
  search field into the `Sheet` drawer the menu button already opens, keep its
  `role="search"` form and its hidden label, and say that you did so.
- At `lg` and above the layout must not regress: one row, wordmark, the primary `<nav>`, the
  visible search field, the compact language switcher, the cart at the far right.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/components/SiteHeader.tsx`
- `storefront/src/components/MobileNav.tsx`
- `storefront/src/components/CartLink.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. In particular do not touch
`storefront/src/lib/i18n/**`, `storefront/src/app/globals.css`, `LanguageSwitcher.tsx`,
`ui/Select.tsx`, `ui/Button.tsx`, any page under `storefront/src/app/`, or anything under
`packages/`, `velmor/`, `.cursor/`, `harness/`, `scripts/`, `openspec/`.

## Inputs to read first

- `AGENTS.md`
- `storefront/src/components/SiteHeader.tsx`, `MobileNav.tsx`, `CartLink.tsx`
- `storefront/src/components/ui/Button.tsx` and `ui/Sheet.tsx` (read only, for the classes and
  the drawer contract)
- `storefront/src/app/globals.css` (read only, for the token names)

## Hard rules

- Do not change any user-facing string and do not add a string literal. Every visible label
  comes from the `dict` prop that is already passed in. Do not edit the dictionaries. If you
  need a new string, reply `NEEDS_KEY <dictionary.key>` and stop.
- New copy must not name an environment variable or any internal configuration.
- Use only the CSS custom properties already declared in `globals.css` and the classes already
  exported by `ui/Button.tsx`. Do not add a dependency.
- Keep every existing accessibility contract: the skip link, the `<nav aria-label>`, the
  `role="search"` form with its hidden label, the cart's accessible name and count, and the
  mobile drawer's focus trap and Escape handling. Do not remove an accessible name.
- The wordmark already renders its own anchor and its accessible name; do not wrap it in a
  second link.
- Do not use `position: fixed` to escape the header box - the measurement is of the header's
  own box, and a fixed child that sits outside it still fails outcome 2.
- No `TODO`. Do not run git. Do not run a browser. Nothing that reaches the network.
- **Do not ask me to confirm a design and do not end with a question.** Implement the change.
  If a decision is genuinely ambiguous, pick the option that satisfies the outcome above and
  say what you picked in your reply.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run lint
```

Do not retry a failure. If a command fails, stop and report it.

## Token contract

Keep the change small and local. Reserve enough of the budget to run both commands above. If
the work cannot be finished without dropping scope, reply exactly `CONTEXT_LIMIT` rather than
guessing or leaving the file half-edited.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
