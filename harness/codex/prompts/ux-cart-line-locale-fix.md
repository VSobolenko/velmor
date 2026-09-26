# Fix round: `cart-title-locale` did not pass its own test, and one instruction in the brief was wrong

Your run ended `BLOCKED test:i18n failed: cart-titles.ts imports unsupported @/ aliases in Node
tests`. That verdict is correct and the work is not accepted yet. Four defects follow, each with the
evidence that establishes it. Fix all four, then run the gates.

## 1. The module cannot be imported by the test runner (the blocker you reported)

`storefront/src/lib/cart-titles.ts` imports `CommerceApiClient` and `CommerceApiError` from `@/lib/api`
as **values**. The suite runs as plain `node --test "test/**/*.test.ts"` (`storefront/package.json`
line 11). Node strips types; it does not read `tsconfig.json` `paths`, so `@/...` cannot resolve and
the module never loads. Measured: `npm --prefix storefront run test:i18n` is `pass 54 / fail 1`, and
the single failure is `test/cart-titles.test.ts`.

The resolvable form is a relative specifier with an explicit `.ts` extension, which is what the
modules that are already tested this way use:

- `storefront/src/lib/api/client.ts` line 1 reads `import type { Locale } from "@/lib/i18n";` - it is
  the file's only `@/` import, and it is **type-only**, so the stripper erases it and the module loads.
- `storefront/test/api-client.test.ts` line 3 reads
  `import { CommerceApiClient } from "../src/lib/api/client.ts";` and passes.
- `storefront/tsconfig.json` line 12 sets `"allowImportingTsExtensions": true`, so the extension is
  legal for the type check as well.

So import the two classes from `"./api/client.ts"` - the canonical file, which exports both
(`client.ts` line 32 `CommerceApiError`, line 46 `CommerceApiClient`). Your type-only imports of
`CartLine` and `Locale` may stay as `@/` imports: they are erased and cost nothing.

Your own test file already gets this right; it is the source module that does not.

## 2. Remove the `title` field from the checkout request body

Your diff adds `title: line.title` to the lines posted to `/checkout/start`. That was asked for in the
brief and the brief was wrong. Do not send it.

- `packages/api/src/app.py` lines 62-69: `CheckoutLineBody` declares exactly `candidate_id`,
  `unit_amount`, `quantity`, with `model_config = {'frozen': True}`.
- The handler reads exactly those three when it builds the domain line: `app.py` lines 530-532,
  `CartLine(candidate_id=..., unit_amount=..., quantity=...)`.
- Pydantic's default for an undeclared field is `extra='ignore'`, and this model does not set
  `extra='forbid'`. The field is therefore dropped without an error - it cannot make the order record
  the title, and it never reaches the order.

A field that is silently discarded while looking like it does something is worse than no field. The
body you post must stay exactly `candidate_id`, `unit_amount`, `quantity`. If you believe the order
should record the title the buyer saw, that is a server-side change in `packages/api`, it is not in
this scope, and you must not make it.

## 3. Replace the `try/catch` in `resolveCartTitles`

`cart-titles.ts` currently catches per line. This repository resolves a list of per-item lookups
without a catch, in a page you were told to read the neighbours of:

`storefront/src/app/[locale]/account/entitlements/page.tsx` lines 69-80 collects one
`Promise.allSettled` and `resolvedTitle` (lines 53-64) inspects each settled result once, keeps the
line for a `CommerceApiError` with `status === 404`, and **rethrows everything else**. `account/orders/[orderId]`
does the same. Follow that shape: one `Promise.allSettled` over the lines, then map the settled
results, returning the stored line for a withdrawn good and rethrowing anything else. No `try`, no
`catch`.

## 4. The list you render must follow the live cart, not a copy of it

`useCartTitles` keeps its own `resolvedLines` array and returns that. The rendered list is therefore a
snapshot: when the buyer removes a line or changes a quantity, `lines` changes at once but the screen
still shows the previous array until the network answers. On a slow connection a removed line stays
visible and a quantity change does not appear.

Keep a map of resolved titles keyed by `candidate_id` and derive the displayed lines from the current
`lines` on every render:

```
const [titles, setTitles] = useState<Record<string, string>>({});
const displayLines = lines.map((line) => ({ ...line, title: titles[line.candidate_id] ?? line.title }));
```

so the structure always follows the live cart and only the titles are patched in. A line with no
resolved title keeps its stored snapshot, which is the behaviour the brief requires.

Note for your `useEffect` dependencies: `lines` comes from `useSyncExternalStore` via `CartProvider.tsx`
line 58 and is referentially stable between renders unless the cart actually changes (`cart.ts` lines
87-94 cache the snapshot). Your effect will not loop as written, but do not widen the dependencies in
a way that breaks that.

## 5. Restore the indentation you dropped

`storefront/src/app/[locale]/cart/page.tsx`: your edit turned `{lines.map((line) => {` into
`{displayLines.map((line) => {` and lost the two leading spaces the surrounding block has. Put them
back; the file is otherwise indented consistently and `next build` type-checks what you leave behind.

## 6. Your regression test must still fail on the old behaviour

The brief required it and it still applies: a test that passes against both the old and the new
behaviour is not evidence. State in your reply which assertion fails when the resolution is removed.

## Scope

Unchanged from the brief. You may write only:

- `storefront/src/lib/cart-titles.ts`
- `storefront/src/app/[locale]/cart/page.tsx`
- `storefront/src/app/[locale]/checkout/page.tsx`
- `storefront/test/cart-titles.test.ts`

`storefront/src/lib/cart.ts` is now off the list: do not change what a stored line holds. Do not touch
`packages/`. Do not add a dependency.

## Verification boundary

Run exactly these, in this order, and quote the last lines of each in your reply:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run test:i18n
npm --prefix storefront run build
```

`test:i18n` must report `pass 55 / fail 0`. Before it reported `pass 54 / fail 1`. Do not retry a
failure: if a command fails, stop and report it.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
