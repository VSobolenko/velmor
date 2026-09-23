# Task: stop the add-to-cart button printing two labels on top of each other

## Outcome

No button in the shop renders two labels overprinted. Measured in the DOM on the running site:

- For every add-to-cart button, exactly one of its two label strings is visible; the other is
  hidden visually while still reserving its width, so the button's size never changes between
  states.
- The button's `innerText` is a single label, not two.

Today `AddToCartButton` renders `В корзину` and `Добавлено` in the same grid cell with only
`aria-hidden` differing, so both are painted on top of each other. A DOM audit found 12-24 such
collisions on every page, in `ru`, `en` and `be`. `Button` has the same defect for its
`loadingLabel`.

## Scope

Working directory: the repository root.

You may WRITE only these two files:

- `storefront/src/components/AddToCartButton.tsx`
- `storefront/src/components/ui/Button.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. Do not touch `storefront/src/lib/i18n/**`,
`storefront/src/app/globals.css`, `SiteHeader.tsx`, `ui/Select.tsx`, `LanguageSwitcher.tsx`,
`MobileNav.tsx`, `ProductCard.tsx`, or anything under `packages/`, `velmor/`, `.cursor/`,
`harness/`, `scripts/`, `openspec/`.

## The defect, already diagnosed, do not re-investigate

`storefront/src/components/AddToCartButton.tsx` ends with:

```tsx
<span className="grid">
  <span className="col-start-1 row-start-1" aria-hidden={added}>
    {label}
  </span>
  <span className="col-start-1 row-start-1" aria-hidden={!added}>
    {addedLabel}
  </span>
</span>
```

Both spans are always rendered and both are `visibility: visible`, `opacity: 1`. `aria-hidden`
removes a node from the accessibility tree; it does not hide it visually. Confirmed on the live
site: the button's `innerText` is `В корзину\nДобавлено`.

`storefront/src/components/ui/Button.tsx` has the same shape: when `loading` is true, `children`
and `busyLabel` are both rendered in one cell.

## The fix

Keep the intent that the comment in `AddToCartButton` states — both labels share one grid cell so
the button is as wide as the wider of the two and a state change never moves the layout — and
make the inactive label invisible without removing it from the layout.

A `visibility: hidden` style, or an equivalent utility class that sets it, satisfies both
requirements. Removing the second span entirely would lose the stable width and is not
acceptable; adding a fixed `min-width` instead is acceptable only if it is derived from the
labels and documented in the comment.

Apply the same correction to the `loadingLabel` case in `Button`.

## Hard rules

- Do not change either component's public props: `candidateId`, `title`, `unitAmount`,
  `currency`, `label`, `addedLabel`, `size`, `className` stay as they are, and `variant`, `size`,
  `loading`, `loadingLabel`, `disabled` stay as they are. A caller in a file you may not touch
  (`ProductCard.tsx`, `BuyBox.tsx`, `StickyBuyBar.tsx`, `RelatedGoods.tsx`) must keep working.
- Do not change any user-facing string. Do not edit the dictionaries.
- Use only the CSS custom properties already declared in `globals.css`.
- Keep the accessible name correct: when the good is in the cart, the exposed name is the
  `addedLabel` and the other label stays out of the accessibility tree.
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
