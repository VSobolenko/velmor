# The type check fails: the narrowed provider id does not reach `startCheckout`

Your change is in place and `npm --prefix storefront run check:i18n` and
`npm --prefix storefront run lint` both pass, but the production build fails. `lint` does not run
a type check, so it could not have caught this. The real gate output:

```
npm --prefix storefront run build
src/app/[locale]/checkout/page.tsx(173,9): error TS2322: Type 'string | null' is not assignable to type 'string'.
Failed to type check.
```

## Cause

`providerId` is now `string | null`, because it starts as `null` until the provider list
arrives. `onPay` guards it at runtime:

```ts
if (providerId === null) {
  return;
}
void startCheckout(payCurrency);
```

But a runtime guard does not narrow the type inside `startCheckout`, which reads the state value
directly for the request body:

```ts
provider_id: providerId,
```

TypeScript sees `string | null` there and rejects it. Do not fix this with a non-null assertion,
a cast, or `as string`: the point of the guard is that the value is proven present, and an
assertion discards the proof instead of carrying it.

## The fix

Carry the value across the boundary. Give `startCheckout` the provider id as a parameter:

```ts
async function startCheckout(payCurrency: string, provider: string): Promise<void>
```

and use that parameter in the request body. `onPay` already establishes the value before calling
it, so it passes `providerId` there and the narrowing holds at the call site.

If you find a cleaner arrangement that keeps the proof — for example resolving the provider id
once at the top of `onPay` into a local constant, checking it, and passing that constant — use
it. What is not acceptable is an assertion, a cast, or narrowing by `!`.

Leave every other behaviour exactly as it is: the acknowledgement gate and its required message,
the `payingRef` in-flight guard, the disclosure states, the empty-cart state, the fallback label
for an unknown provider id, and the dictionaries.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/app/[locale]/checkout/page.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file.

## Hard rules

- No `as string`, no `!`, no `as any`, no `@ts-expect-error`, no `@ts-ignore`.
- No behaviour change beyond what is needed to make the type check pass.
- Do not add a dependency. No `TODO`. Do not run git.
- **Do not ask me to confirm anything and do not end with a question.** Implement the change.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run build
```

`npm run build` is the type check and must pass. Do not retry a failure: if a command fails,
stop and report it.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
