# Task: make the account entry cards clickable as a whole, and stop showing buyers an env var name

## Outcome

On the running storefront at `/ru/account` (and the same page in `be` and `en`):

1. Each of the two entry cards is ONE link whose hit area covers the whole card. Measured on
   the deployed site at a 390 px viewport, the card is `343x94` while the current anchor is
   only `61.8x24` (first card) and `153.6x24` (second): the anchor must instead cover the card
   and be at least 44 px tall.
2. No buyer-visible text on the account surface names an environment variable or any internal
   configuration. Today the note above the cards reads, in `ru`,
   `Идентификатор покупателя — демо-заголовок NEXT_PUBLIC_BUYER_ID, пока нет настоящей авторизации.`
   and the `en` and `be` entries name the same variable.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/app/[locale]/account/page.tsx`
- `storefront/src/lib/i18n/en.json`
- `storefront/src/lib/i18n/ru.json`
- `storefront/src/lib/i18n/be.json`

You may READ anything under `storefront/src/`.

You may NOT write any other file. In particular do not touch
`storefront/src/components/ui/Card.tsx`, any other page, `globals.css`, or anything under
`packages/`, `velmor/`, `.cursor/`, `harness/`, `scripts/`, `openspec/`.

## Current code, already read - do not re-investigate

`storefront/src/app/[locale]/account/page.tsx` builds an `entries` array and renders it as
`<li><Card variant="flat" className="flex h-full flex-col gap-1">` containing an `h2` whose
child is the only `<Link href={entry.href}>`, followed by the hint `<p>`. Only that anchor is
clickable, which is why the hit area is the height of the title text.

The whole-card-link pattern already exists in this repository: `ProductCard.tsx` makes the
card's title link cover the card with Tailwind's `after:absolute after:inset-0` on the anchor,
with the card as the positioning context. Reuse that exact technique rather than inventing a
second one, and keep the hint text inside the card's visual bounds.

## Hard rules

- Every visible string comes from the dictionary via `dict[...]`. Do not put a string literal
  in the component. Do not name an environment variable, a config key or a code concept in any
  buyer-facing copy.
- Keep the three dictionaries key-for-key identical: the parity check
  (`npm --prefix storefront run check:i18n`) must pass. If you add, remove or rename a key, do
  it in all three files in the same change.
- The replacement note must say the same thing in all three locales. Required meaning: the
  demo shop has no sign-in yet, so orders and downloads are shown for a single demonstration
  buyer. Write it as ordinary buyer-facing prose: no env var names, the words "header",
  "token", "variable", "configuration" or "API" must not appear, and it must not read like a
  developer comment.
- Keep the existing structure: the `h1`, the two cards in the existing grid, the
  `Card` component and its variants, and the routes the cards point at.
- Do not change the header, the cart, or any other route.
- No new dependency. No `TODO`. Do not run git. Do not run a browser. Nothing that reaches the
  network.
- **Do not ask me to confirm wording and do not end with a question.** Implement the change.

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
guessing or leaving a file half-edited.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
