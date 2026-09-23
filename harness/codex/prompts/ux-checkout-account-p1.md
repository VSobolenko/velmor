# Task: make the account, cart and checkout controls reachable by touch, and explain the disabled pay action

## Outcome

Measured in the DOM at 390x844 and 1440x900 on the live Proofbasket storefront:

- Every interactive control in the account, cart and checkout pages is at least 44x44 px.
  Today: the account tabs are 24 px tall (`Заказы` at 62x24, `Права на загрузку` at 154x24), the
  checkout licence checkbox is 20x20 px, and the cart line-item title link is 22 px tall.
- The `Оплатить` button on checkout, while it is disabled, states in the active locale why it
  cannot be used yet, and that explanation disappears once the licence acknowledgement is ticked.
  Today the button is disabled with no visible reason.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/components/ui/Checkbox.tsx`
- `storefront/src/components/ui/Tabs.tsx`
- `storefront/src/app/[locale]/cart/page.tsx`
- `storefront/src/app/[locale]/checkout/page.tsx`
- `storefront/src/app/[locale]/checkout/return/page.tsx`
- `storefront/src/app/[locale]/account/page.tsx`
- `storefront/src/app/[locale]/account/orders/page.tsx`
- `storefront/src/app/[locale]/account/orders/[orderId]/page.tsx`
- `storefront/src/app/[locale]/account/entitlements/page.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. In particular you may NOT touch:

- `storefront/src/lib/i18n/**` (shared dictionaries; another worker owns them)
- `storefront/src/app/globals.css` (the tokens are WCAG-tuned)
- `SiteHeader.tsx`, `ui/Select.tsx`, `ui/Button.tsx`, `AddToCartButton.tsx`, `ProductCard.tsx`
  (other workers own those)
- `storefront/src/components/DownloadButton.tsx`, `OrderStateBadge.tsx`, `CartProvider.tsx`,
  `ui/Button.tsx`
- any file under `packages/`, `velmor/`, `.cursor/`, `harness/`, `scripts/`, `openspec/`

## Inputs you must read first

- `AGENTS.md`
- the files listed in Scope (the current code)
- `storefront/src/app/globals.css` (read only: the token names you must use)
- `.cursor/skills/storefront-ux/SKILL.md` (read only: the design-system contract and the states)
- `.cursor/rules/07-product-surface.mdc` (read only: the minimum bar for cart, checkout, account)

## The rules that bind this task

- Every interactive control has a target of at least 44x44 px, with a visible focus indicator.
- No action is hover-only.
- The checkout has: an order summary, a provider choice, the seller disclosure, and a required
  licence acknowledgement. The acknowledgement is required before payment, and the state of the
  primary action must be perceivable as disabled and its reason must be readable.
- Every state is designed: loading, empty, error, unauthenticated.
- A legal disclosure is not decoration: a buyer must know what they are permitted to do before
  the transaction. Do not weaken the acknowledgement requirement to make the button easier to
  enable.

## Hard rules

- Changes to `Checkbox` and `Tabs` must be additive: a caller that passes nothing keeps the
  current rendering, apart from the target size, which may only grow. Do not rename or remove a
  prop.
- Every user-facing string must come from the dictionary already passed in. Do not add a literal.
  Do not edit the dictionaries. If the explanation for the disabled pay button needs a string
  that does not exist yet, reply `NEEDS_KEY <dictionary.key>` and stop instead of inventing one.
  Search the existing dictionaries first: a suitable key may already exist.
- Use only the CSS custom properties already declared in `globals.css`.
- Do not change the checkout's business behaviour: do not auto-mark an order paid, do not make
  the acknowledgement optional.
- No new dependency. No `TODO`. Do not run git. Nothing that reaches the network.
- Keep each file's existing style: TypeScript, 2-space indent, double quotes.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run lint
```

Do not retry a failure. If a command fails, stop and report it.

## Token contract

Stay within a modest budget; reserve enough for the two commands and the handoff. If the work
cannot be completed without dropping scope, reply exactly `CONTEXT_LIMIT`.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
