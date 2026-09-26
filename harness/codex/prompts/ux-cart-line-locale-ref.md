# Fix round 3: drop the ref - the staleness guard it was for does not need one

You replied `BLOCKED lint failed: react-hooks/refs forbids updating keyRef.current during render`.
That is a real lint error, and the instruction that produced it came from the previous brief, not from
you. The previous brief said: "Guard against a stale async result landing under a new key by checking
the key in the `.then` before storing it, instead of relying on the `cancelled` flag alone." That
instruction pushed you into a ref written during render, which `react-hooks/refs` forbids. The guard it
asked for is unnecessary. Withdraw it.

## Why no guard is needed

The effect closure already captures the `key` it was started for. `setResolved({ key, titles })` stores
that captured key. `loading` is derived by comparing the **stored** key against the **current** key:

```
const loading = lines.length > 0 && resolved?.key !== key;
```

A result that arrives late stores the key it was resolved for, which is by then not the current key, so
`loading` stays true and the stale titles are simply not presented as fresh. There is nothing to guard
against and no ref to hold. The only thing `cancelled` still does is stop a `setState` after unmount.

## The change

In `storefront/src/lib/cart-titles.ts`:

- Delete the ref entirely. No `useRef`, and nothing read or written during render.
- Keep one state value holding the resolved titles and the key they were resolved for.
- Derive `key` from the locale and the candidate ids of the current lines.
- Derive `loading` from the stored key versus the current key, as above.
- Derive `displayLines` from the live `lines` patched with the stored titles, exactly as it is now.
- The effect body must contain **no synchronous setState at all**: no `setLoading(...)`, no
  `setFault(null)`. The only `setState` calls are `setResolved(...)` in the `.then` and `setFault(...)`
  in the `.catch`, both asynchronous.
- Keep returning `{ lines: displayLines, loading }` so neither page has to change.

Two lint rules are live on this file and the change must satisfy both at once:

- `react-hooks/set-state-in-effect` - no setState synchronously in the effect body.
- `react-hooks/refs` - no ref read or write during render.

If a third mechanism occurs to you, prefer deriving from `key` over adding state or a ref: the state
this hook needs is exactly one value, and everything else is a derivation.

## Scope

Only `storefront/src/lib/cart-titles.ts`. Do not touch the two pages, `cart.ts`, or the test.

## Verification boundary

Run exactly these two, in this order, and quote the last lines of each:

```
npm --prefix storefront run test:i18n
npm --prefix storefront run lint
```

`test:i18n` must stay `pass 55 / fail 0`. `lint` must report no problems.

Do **not** run `npm --prefix storefront run build`: it needs the network for Google Fonts and cannot
succeed in your sandbox. It is outside your boundary, not a failure.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
