# Task: give the root 404 the same skip link as every other page

## Outcome

The root not-found surface renders the same skip link that `storefront/src/app/[locale]/layout.tsx`
renders on every localised page.

Measured on the deployed site: on `/ru/account` and every other localised page the header row
contains an anchor with the text from `dict["common.skipToContent"]` (`Перейти к содержимому` /
`Перайсці да змесціва` / `Skip to content`), carrying the class
`sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-ink`
and `href="#content"`. The root `storefront/src/app/not-found.tsx` renders `SiteHeader`,
`/ru/account`-style `main` and `SiteFooter` itself, but renders no such anchor, so the surface
that handles a request which never reached a locale segment is the only one missing it.

## Scope

Working directory: the repository root.

You may WRITE only this file:

- `storefront/src/app/not-found.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. In particular do not touch
`storefront/src/app/[locale]/layout.tsx` (read it, do not change it), the dictionaries, any
component, or anything under `packages/`, `velmor/`, `.cursor/`, `harness/`, `scripts/`,
`openspec/`.

## Required change

Render one anchor, before `SiteHeader`, with `href="#content"`, the class string copied exactly
from `storefront/src/app/[locale]/layout.tsx`, and the label `dict["common.skipToContent"]`.
The `main` element in the same file already carries `id="content"`, so the anchor's target
already exists. The label must come from the dictionary; do not write the string literally.

## Hard rules

- Do not add or rename a dictionary key. `common.skipToContent` already exists in all three
  locales. If you believe a key is missing, reply `NEEDS_KEY <dictionary.key>` and stop.
- Do not restructure the file, do not change the `CartProvider` wiring, the locale resolution
  or the existing heading, body and link.
- Keep the three dictionaries untouched, and keep the parity check passing.
- No new dependency. No `TODO`. Do not run git. Do not run a browser. Nothing that reaches the
  network.
- **Do not ask me to confirm and do not end with a question.** Implement the change.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run lint
```

Do not retry a failure. If a command fails, stop and report it.

## Token contract

This is a one-element change. If the work cannot be finished without dropping scope, reply
exactly `CONTEXT_LIMIT`.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
