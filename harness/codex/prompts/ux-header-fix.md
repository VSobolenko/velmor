# Follow-up: the header breaks at exactly 768 px, and the cart is not in the right cluster on mobile

Your previous change is in place and the header is now 65 px tall at every width, down from 165 px
and 217 px. Two measured defects remain. Both were measured on a production build.

## Defect 1: the desktop header does not fit at 768 px

Measured at 768x900 on `/ru`:

```
overCount: 2
SPAN ""                          l=711 r=776 w=65   <- the cart's visible label
SPAN "inline-flex min-w-6 ..."   l=780 r=804 w=24   <- the cart's count badge
```

The cart's label and count badge extend past the 768 px viewport, so the cart is visibly cut off
at tablet width. The cause is the breakpoint: the desktop arrangement is switched on at `md`
(768 px), but it only fits from 1024 px upward. Measured at 1024 px: `hOver: 0`,
distance from the cart to the right edge 31 px. The mobile arrangement fits at 390 px.

Fix: move the desktop arrangement's breakpoint from `md` (768 px) to `lg` (1024 px), and keep the
compact mobile arrangement below that. That means the desktop-only pieces — the primary `<nav>`,
the search `<form>`, and the language switcher — become visible only from `lg`, and the mobile
menu, its search toggle and its hamburger stay visible until `lg`.

## Defect 2: on mobile the cart is not in the right-hand cluster

Measured at 390x844 on `/ru`: the distance from the cart's right edge to the viewport's right edge
is 130 px, because the row reads wordmark, cart, search toggle, hamburger, all packed to the left.
The cart must be in the right-hand cluster: wordmark on the left, then the cart, the search toggle
and the hamburger grouped on the right, with the cart's count badge fully visible.

Note on how the existing layout pushes content right: on desktop the search `<form>` carries
`ml-auto` and absorbs the free space, which is correct and must not change. Because the form is
hidden below `lg` after Defect 1's fix, the cart needs to absorb the free space at those widths.
An `ml-auto` on the cart that is neutralised from `lg` upward, such as `ml-auto lg:ml-0`, keeps the
desktop behaviour intact and fixes mobile. Verify you did not end up with two elements competing
for the free space at desktop width.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/components/SiteHeader.tsx`
- `storefront/src/components/MobileNav.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. Do not touch `LanguageSwitcher.tsx`, `ui/Select.tsx`,
`ui/Button.tsx`, `AddToCartButton.tsx`, `CartLink.tsx`, `storefront/src/lib/i18n/**`,
`storefront/src/app/globals.css`, or anything under `packages/`, `velmor/`, `.cursor/`,
`harness/`, `scripts/`, `openspec/`.

## Hard rules

- Keep the header one row: at most 80 px at 1440 px, at most 64 px plus its 1 px border at 390 px.
  It is 65 px today including the border; do not let it grow.
- Keep every accessibility behaviour: the skip link, the `<nav aria-label>`, the `role="search"`
  forms and their hidden labels, the cart's accessible name and count, the mobile drawer's focus
  trap and Escape handling, and 44x44 px targets.
- Do not change any user-facing string and do not edit the dictionaries.
- Use only the CSS custom properties already declared in `globals.css`.
- No new dependency. No `TODO`. Do not run git. Nothing that reaches the network.
- **Do not ask me to confirm a design and do not end with a question.** Implement the change.

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
