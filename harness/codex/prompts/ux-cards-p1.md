# Task: make the product card reach the 44 px target and match the recorded card pattern

## Outcome

On the live Proofbasket storefront, every product card is a valid touch target and matches the
recorded card pattern. Concretely, measured in the DOM at 390x844 and 1440x900:

- Every interactive element inside a card is at least 44 px tall and 44 px wide.
- Today the card title link is 43 px tall, and 21 px tall whenever the title wraps to two lines
  (measured: `Лагерь сигнальной роты` at 256x21, `Фотограф Национального музея` at 292x21).
- Each card shows: a fixed-ratio media box, a title, the creator, a licence badge, the price
  next to the action, an always-visible add-to-cart, and a placeholder when there is no preview.
- The whole card remains clickable and the card never overlaps its own text.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/components/ProductCard.tsx`
- `storefront/src/components/CatalogueGrid.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. In particular you may NOT touch:

- `storefront/src/lib/i18n/**` (shared dictionaries; another worker owns them)
- `storefront/src/app/globals.css` (the tokens are WCAG-tuned)
- `storefront/src/components/AddToCartButton.tsx`, `SiteHeader.tsx`, `ui/Button.tsx`,
  `ui/Select.tsx` (another worker owns those)
- the catalogue page, the product page, the cart, the checkout, the account pages
- any file under `packages/`, `velmor/`, `.cursor/`, `harness/`, `scripts/`, `openspec/`

## Inputs you must read first

- `AGENTS.md`
- `storefront/src/components/ProductCard.tsx` and `CatalogueGrid.tsx` (the current code)
- `storefront/src/components/AddToCartButton.tsx` (read only: it is the action you place; do not
  edit it)
- `storefront/src/app/globals.css` (read only: the token names you must use)
- `.cursor/skills/storefront-ux/SKILL.md` (read only: the card pattern and its sources)

## The rules that bind this task

- Product cards: one fixed image ratio, a dominant image, the price as the anchor near the
  action, one obvious action, the whole card clickable.
- Never hover-only: the add-to-cart is always visible, because a hover-only affordance does not
  exist on a touch device.
- Interactive elements: at least 44x44 px, with visible focus.
- A card is laid out for a 390 px viewport first.
- The source is https://ecomdesignpro.com/product-card-design/ as recorded in
  `.cursor/skills/storefront-ux/SKILL.md`. Do not re-decide the pattern from taste.

## Hard rules

- Do not change the public props of `ProductCard` or `CatalogueGrid` unless a caller requires it;
  if you do, you must update every caller in the files you own and say so in the reply. Callers
  you may not edit: the home page, the catalogue page, the category page, the product page. So
  prefer keeping the current props.
- Every user-facing string must come from the dictionary already passed in. Do not add a literal.
  Do not edit the dictionaries. If you believe a new string is required, reply
  `NEEDS_KEY <dictionary.key>` and stop.
- Use only the CSS custom properties already declared in `globals.css`. No hex colour, no raw
  radius where a token exists.
- No new dependency. No `TODO`. Do not run git. Nothing that reaches the network.
- Keep the file's existing style: TypeScript, 2-space indent, double quotes.
- **Do not ask me to confirm a design and do not end with a question.** Implement the change now.
  A previous worker replied with a request for confirmation and changed nothing; that is a
  failure. If a decision is genuinely ambiguous, pick the option that satisfies the measured
  targets and say what you picked in your reply.

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
