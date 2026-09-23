# The cart titles a good in the language it was added in, not the language being read

Measured on the running shop (`https://shop.78-111-89-46.sslip.io`), in a browser on 2026-09-24,
against the commit deployed at the time (`370f2233`):

- `/en/cart` states `lang="en"` and its chrome is English: `Cart`, `Subtotal`, `each`, `Remove`.
- Its five line titles are in three languages at the same time:

```
Лагерь сигнальной роты, 1898 год                       (ru)
Фотограф Национального музея США                       (ru)
Летоянни, Мессина, Сицилия, Италия — снимок            (ru)
Череп Brachauchenius lucasi, образец USNM 2361         (ru)
Гатэль Ca' Sagredo на Гранд-канале ў Венецыі           (be)
```

- The Belarusian one was added from `/be` seconds before the measurement; the four Russian ones were
  added from `/ru` earlier in the same browser session.
- The English title for that last good exists and the shop uses it everywhere else:
  `/en/goods/openverse:0ccdd09f-d9c2-4aef-ba85-12a8ca214b66` renders `h1`
  `Hotel Ca' Sagredo on the Grand Canal, Venice`.

So the English text is available and the cart does not reach for it. The same effect was seen on
`/be/cart`, where a good whose Belarusian title the catalogue shows (`Лагер сігнальнай роты`) was
listed under its Russian one (`Лагерь сигнальной роты`).

**Cause.** `storefront/src/lib/cart.ts` stores a `title` in every line, written at the moment the good
is added and never recomputed. The line lives in `localStorage`, so the language it carries is the
language of whichever page the buyer happened to be reading when they added it, and it outlives a
change of language.

**The contract this breaks.** `openspec/changes/redesign-storefront-ux/specs/commerce/storefront/spec.md`
states "The shop is served in the buyer's language" and "No screen carries an untranslated string".
That same spec permits a good's Russian text to be shown only when the good has *no* presentation in
the requested language ("A good with no text in the requested language falls back"). This is not that
case: the requested language's text exists.

## The change

A line in the cart and in the checkout SHALL display the good's title in the language the buyer is
reading, not the language the good was added in.

- Keep the stored line's `title`. It stays the snapshot taken at add time and stays the value written
  when a line cannot be resolved (below). Do not widen what is stored.
- The stored line's `candidate_id` is the key for the resolution. Resolve the displayed title through
  the existing locale-aware catalogue client: `CommerceApiClient.getGood` already carries the active
  locale and appends `?locale=`.
- **Do not implement a fallback in the storefront.** The API already owns the "the good has no text in
  this language" rule and returns the documented text. Adding a second fallback here would be a second
  source of truth for a rule the API already decides.
- The checkout posts these lines to `/checkout/start`. What it posts must carry the title for the
  language the buyer is reading, so the order records what the buyer saw.
- A line whose good the catalogue no longer returns must keep rendering its stored snapshot title,
  exactly as it renders today. Do not invent a new cart state, a new string, or a new badge for a
  withdrawn good: that is a separate change and it is not in scope. `CommerceApiError` in
  `storefront/src/lib/api/client.ts` carries `status` and a `reason` of `"refusal"` or `"fault"` for
  exactly this kind of caller decision, and a withdrawn good arrives as a 404 refusal; a `fault` is an
  API failure and must not be rendered as a withdrawn good. Handling that typed outcome is the logic,
  not a swallowed error - do not add a catch that turns any failure into the snapshot.

## Scope

Working root: the repository root.

Read first, in this order:

- `AGENTS.md` - the always-on contract
- `openspec/changes/redesign-storefront-ux/specs/commerce/storefront/spec.md` - "The shop is served in
  the buyer's language" and "No screen carries an untranslated string", including the fallback
  scenario
- `storefront/src/lib/cart.ts` - the stored line and the store itself
- `storefront/src/app/[locale]/cart/page.tsx`
- `storefront/src/app/[locale]/checkout/page.tsx`
- `storefront/src/lib/api/client.ts` - `getGood`, `CommerceApiError`, `CommerceApiFailure`
- `storefront/test/api-client.test.ts` - the existing test style

You may WRITE only these files:

- `storefront/src/lib/cart.ts`
- `storefront/src/app/[locale]/cart/page.tsx`
- `storefront/src/app/[locale]/checkout/page.tsx`
- `storefront/src/lib/cart-titles.ts` - new, and only if both pages need the same resolution
- `storefront/test/cart-titles.test.ts` - new, the regression test

If the change genuinely requires a sixth file, stop and reply `BLOCKED <why>`. Do not edit a file
outside that list. You may READ anything under `storefront/src/` and `storefront/test/`.

## Hard rules

- Every buyer-visible string stays in the three dictionaries. A new literal in a component is a
  defect. Do not add a dictionary key unless a string the buyer reads genuinely has no key yet.
- Do not rename a dictionary key and do not change any existing user-facing string.
- Do not change the price, the quantity controls, the totals, the removal, or anything the checkout
  posts other than the title's language.
- Do not add a dependency. No `TODO`. Do not run git. Nothing that reaches the network.
- Keep keyboard operability and the accessible name of every control.
- The regression test must fail on today's behaviour and pass on the new one. Prove that by running it
  before and after; a test that passes both ways is not evidence.
- `npm --prefix storefront run build` runs a type check and must pass. `lint` does not run a type
  check, so it is not a substitute.
- **Do not ask me to confirm a design and do not end with a question.** Implement the change.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run test:i18n
npm --prefix storefront run build
```

Do not retry a failure. If a command fails, stop and report it. No network commands: the test must
not call the live API, so inject the resolver rather than fetching.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
