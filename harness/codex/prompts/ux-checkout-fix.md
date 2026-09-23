# Task: correct the licence-acknowledgement state on the checkout page

## Outcome

On the checkout page, measured on the running site at 390x844 and 1440x900, in `ru`:

- The licence acknowledgement is a control of at least 44x44 px, and it is the shared
  `Checkbox` from `@/components/ui/Checkbox`.
- The validation message `dict["checkout.licenceAckRequired"]` is NOT shown when the page first
  renders. It appears only after the buyer has tried to pay with the acknowledgement unticked,
  and it disappears as soon as the acknowledgement is ticked.
- The `Оплатить` button is disabled until the acknowledgement is ticked, and while disabled the
  page states why.

## Context: a previous worker started this and left it wrong

`storefront/src/app/[locale]/checkout/page.tsx` was already changed by a previous worker. Its
edits are correct in direction but wrong in one respect: it deleted the `acknowledgementMissing`
state and now renders the alert whenever `!accepted`, so a buyer who has done nothing yet is shown
an error on arrival. That is the regression you must fix.

Do not revert the `Checkbox` usage. Keep it. Restore the "show the message only after an
attempt" behaviour.

## Scope

Working directory: the repository root.

You may WRITE only this file:

- `storefront/src/app/[locale]/checkout/page.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. Do not touch `storefront/src/lib/i18n/**`,
`storefront/src/app/globals.css`, `ui/Checkbox.tsx`, `ui/Button.tsx`, or anything under
`packages/`, `velmor/`, `.cursor/`, `harness/`, `scripts/`, `openspec/`.

## Inputs to read first

- `AGENTS.md`
- `storefront/src/app/[locale]/checkout/page.tsx` (the current, partly-correct code)
- `storefront/src/components/ui/Checkbox.tsx` (read only: its `label`, `checked`,
  `onCheckedChange` props)

## Hard rules

- The acknowledgement stays required. Do not make payment possible without it. Do not auto-tick
  it. Do not weaken the legal disclosure.
- Prefer a string that already exists in the dictionaries. Do not edit the dictionaries and do
  not add a literal. If you need a new key, reply `NEEDS_KEY <dictionary.key>` and stop.
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
