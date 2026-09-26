# Fix round 2: `cart-titles.ts` fails the documented lint gate

Your round-2 change is correct on all four defects from the previous brief, and `test:i18n` now
reports `pass 55 / fail 0`. One gate still fails, and it was left out of the previous brief's
verification list, which is why you did not see it.

## The defect

`npm --prefix storefront run lint` reports:

```
D:\Python\Velmor\storefront\src\lib\cart-titles.ts:52:5
  50 |     let cancelled = false;
  51 |     const client = CommerceApiClient.fromEnv(locale);
> 52 |     setLoading(lines.length > 0);
     |     ^^^^^^^^^^ Avoid calling setState() directly within an effect
  53 |     setFault(null);
  54 |     void resolveCartTitles(lines, async (candidateId) => {
  55 |       const good = await client.getGood(encodeURIComponent(candidateId));
     react-hooks/set-state-in-effect

✖ 1 problem (1 error, 0 warnings)
```

Line 52 `setLoading(...)` and line 53 `setFault(null)` both run synchronously in the effect body. The
rule is `react-hooks/set-state-in-effect` and it is an error, not a warning, so `lint` fails.

## The change

Do not suppress the rule and do not move the two calls around. Remove the synchronous writes by
deriving what the effect was trying to store.

- Keep **one** piece of state: the last resolved result together with the key it was resolved for.
- Derive the key from what the resolution depends on - the locale and the candidate ids of the current
  lines - so it changes exactly when a re-resolution is genuinely needed.
- Derive `loading` from that state instead of storing it:
  `loading` is true when there are lines and the stored key is not the current key.
- Let only the asynchronous callbacks write state: the `.then` stores the resolved result under its
  key, and the `.catch` stores the fault. Drop the `setFault(null)` reset: a fault is rethrown during
  render, so the error boundary replaces this subtree and there is no later render of this instance to
  clear it for.
- Keep the derived `displayLines` exactly as it is now - the live `lines` patched with resolved titles
  - and keep returning `{ lines: displayLines, loading }` so neither page changes.

The shape, which you should adapt rather than transcribe blindly:

```
const key = `${locale}|${lines.map((line) => line.candidate_id).join(",")}`;
const [resolved, setResolved] = useState<{ key: string; titles: Record<string, string> } | null>(null);
const displayLines = lines.map((line) => ({
  ...line,
  title: resolved?.titles[line.candidate_id] ?? line.title,
}));
const loading = lines.length > 0 && resolved?.key !== key;
```

and inside the effect only `setResolved(...)` in the `.then` and `setFault(...)` in the `.catch`.

Guard against a stale async result landing under a new key by checking the key in the `.then` before
storing it, instead of relying on the `cancelled` flag alone.

## Scope

Only `storefront/src/lib/cart-titles.ts`. Do not touch the two pages, `cart.ts`, the test, or
`packages/`. If the test needs a change to keep passing, say so in your reply instead of changing it.

## Verification boundary

Run exactly these two, in this order, and quote the last lines of each:

```
npm --prefix storefront run test:i18n
npm --prefix storefront run lint
```

`test:i18n` must stay `pass 55 / fail 0`. `lint` must report no problems.

Do **not** run `npm --prefix storefront run build`. It needs the network to fetch Google Fonts and
cannot succeed in your sandbox; it has already been verified to pass outside the sandbox for this
change. Treat it as out of your boundary, not as a failure.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
