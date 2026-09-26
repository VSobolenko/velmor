# Build: buyer accounts, part 2 - the storefront surface

Implement tasks 4.1 to 4.8 of `openspec/changes/add-buyer-accounts/tasks.md`. Do not edit `tasks.md`;
the orchestrator marks it after verifying your work.

## Read this before you run anything

**The shell in this environment is slow, and it is what killed a previous worker.** Measured on that
run: `git status --short` took 34.9 seconds, `git diff --numstat` took 47.8 seconds, and one command was
killed at the tool limit of 22.8 seconds. The worker ran out of budget on shell round-trips, not on the
problem.

So, for this task:

- **Do not run any `git` command.** Not `status`, not `diff`, not `log`.
- **Do not run exploratory shell commands.** No `ls`, no `find`, no `cat`, no `grep`. Use the file reader
  and the search tool instead.
- **Run only the four verification commands below**, once each, at the end.
- Plan before writing, and batch your edits.

A single misplaced `git diff` costs more time here than the code does.

## Read first, in this order

- `AGENTS.md` - the always-on contract.
- `.cursor/rules/07-product-surface.mdc` - canonical for anything a buyer sees.
- `.cursor/skills/storefront-ux/SKILL.md` - the map: the design system's component contract, the
  "Adding a page" procedure, the layout rules with their sources, and the visual checklist. Follow it.
- `openspec/changes/add-buyer-accounts/specs/commerce/storefront/spec.md` - the behaviour, requirement
  by requirement, including every state a buyer can reach.
- `openspec/changes/add-buyer-accounts/design.md` - the section "Buyer-facing surfaces" gives the
  exact locale keys, the states and the pages.
- `storefront/src/lib/api/client.ts` - the client you are changing.
- `storefront/src/lib/i18n/` - `ru.json`, `be.json`, `en.json`, `paths.ts`, `use-locale.ts`.
- `storefront/src/components/SiteHeader.tsx` and `CartProvider.tsx`.

## The API contract you are calling

The backend provides these routes. Do not invent others and do not call the API's internal shape
directly; add typed methods to `CommerceApiClient`.

| Route | Body | Result |
|---|---|---|
| `POST /auth/register` | `{ email, password, display_name }` | creates the account and signs in; returns the profile |
| `POST /auth/session` | `{ email, password }` | signs in; returns the profile |
| `DELETE /auth/session` | none | signs out |
| `GET /auth/me` | none | the signed-in buyer's `{ id, email, display_name }` |
| `POST /auth/password` | `{ current_password, new_password }` | changes the password |

A refusal arrives as a non-2xx response whose JSON body carries `detail` and `reason`. **`reason` is the
contract and `detail` is not.** `reason` is a stable machine code from this fixed set, and it is what the
storefront switches on to choose a locale key:

| `reason` | meaning |
|---|---|
| `email_required` | the address was empty |
| `email_unavailable` | that address already has an account |
| `invalid_credentials` | wrong password, or no such account - deliberately indistinguishable |
| `password_too_short` | the new password is shorter than the minimum |
| `current_password_incorrect` | the current password did not match |
| `rate_limited` | too many failed sign-ins for that account in the window |
| `unauthenticated` | no valid session was presented |

`detail` is an English sentence assembled by the API and is for logs and developers. **Never render
`detail` to the buyer**; render the locale key you selected from `reason`. A `password_too_short` body also
carries `minimum_length`, a number, which you may show beside the copy because the API owns it.

The existing `CommerceApiError` already carries `status`, `detail` and `reason`; use it, and add the
`minimum_length` field it needs. A `reason` you do not recognise falls back to a generic localized
result-incomplete string rather than to `detail`.

## The client changes, which are the load-bearing part

`storefront/src/lib/api/client.ts`:

1. **Delete `BUYER_HEADER` and `buyerId` entirely.** No request may set `X-Buyer-Id`, and
   `fromEnv` must no longer read `NEXT_PUBLIC_BUYER_ID`. That variable is removed from
   `storefront/.env.example` in the same change.
2. **Browser calls go to the same origin.** A browser-side client uses the relative base `/api`, so the
   session cookie the API set is sent first-party and automatically - no `credentials` option is
   needed for a same-origin request, and none is set.
3. **Server-side calls must forward the cookie explicitly, and this is the part that is easy to get
   wrong.** The account pages are server components (`/account/orders`, `/account/orders/[orderId]`,
   `/account/entitlements`, and the new pages). A `fetch` made on the Next server does NOT carry the
   browser's cookie. So a server-side client resolves the caller's cookie with
   `const store = await cookies()` from `next/headers`, and passes `store.toString()` as a `Cookie`
   request header, while keeping an absolute base URL for the API.
   Implement this as two constructors that share one `requestJson`: a browser one and an
   async server one. Do not let the server path silently send no cookie - an account page that always
   looks unauthenticated is exactly the failure this has to avoid.
4. **`saveDownload` no longer needs a header.** With a same-origin cookie a plain navigation to
   `/api/downloads/<token>` is authenticated by the cookie. Update the method and its comment, which
   currently explains why a header was needed; that reason is gone.

## The pages

Build exactly the pages and keys the design's surface table lists, in all three locales:

- `/[locale]/account/sign-in` and `/[locale]/account/sign-up`: client components. Each is a `Card` with
  labelled `Input`s, one primary `Button`, and a link to the other page. Both must render idle,
  submitting (the button shows it is working and cannot be submitted twice), refused (the reason from
  the API, with what the buyer typed preserved), and service-unavailable (a `ErrorState` naming that
  the service is unavailable, with a way to try again).
- `/[locale]/account/profile`: shows the buyer's email and display name. Never a password.
- `/[locale]/account/password`: asks for the current password and the new one, states the minimum
  length, confirms success, and shows a refusal naming what must change.
- Gate the existing account pages on the session. A visitor with no session opening `/account`,
  `/account/orders`, `/account/orders/<id>`, `/account/entitlements`, `/account/profile` or
  `/account/password` is shown how to sign in and sees no order, entitlement or download. The links
  that lead to sign-in carry the current path so the buyer returns where they were.
- Header (`SiteHeader.tsx`): with no session it offers an action to sign in and does NOT offer the
  account; with a session it shows the buyer's display name and an action to sign out.
- Checkout: a buyer with no session is shown a sign-in prompt with a link back to checkout instead of
  the payment form. The cart lives in `localStorage` and must survive the sign-in round trip unchanged -
  do not clear it on sign-in, sign-out or locale change.

## Locale keys

Add every key in the design's surface table to `ru.json`, `be.json` and `en.json`, and **remove
`account.demoNote` and `checkout.buyerDemoNote` from all three**. Those two tell the buyer they are
shopping as one shared demonstration buyer, which stops being true once buying requires an account.
Removing them is part of this task, not a follow-up.

Do not write the minimum password length into a dictionary: the API owns the number, and the copy
states the rule without restating the value.

## Bring the storefront's own test suite into a gate (task 4.8)

`npm --prefix storefront run test:i18n` runs 55 tests and **no gate runs it** - `lint` is
`check:i18n && eslint`. Change `lint` to run the suite too, so a broken test fails the documented
gate. Then prove the sensor can fail: break one assertion, watch `lint` fail, restore it. Report the
before and after.

## Constraints

- Storefront only. Do not edit anything under `packages/`, `velmor/`, `.deploy/`, `harness/`,
  `.cursor/` or `openspec/`.
- Every buyer-visible string comes from the locale dictionaries. A literal in a component is a defect,
  and `ui-guard` will refuse the write. `aria-label` values are buyer-visible too.
- Do not hardcode a language and do not choose the language from the account. The locale comes from the
  address, as everywhere else in this shop.
- No new dependency. No `TODO`. No compatibility shim. Keep `try/except` out: the existing pages
  distinguish an API failure with `instanceof CommerceApiError` and rethrow anything else, in a
  `catch` that is already there. Follow that existing shape where you need the same distinction; do not
  add a second catch to swallow something.
- Keep every control at a 44 px target and keep its accessible name.

## Verification boundary

Run exactly these, in this order, and quote the last lines of each:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run test:i18n
npm --prefix storefront run lint
npm --prefix storefront run build
```

`check:i18n` must report parity across the three locales, `test:i18n` must pass, and `build` must
succeed. Do not retry a failing command: if one fails, stop and report it. Report the `lint`-fails-
on-a-broken-assertion experiment from task 4.8 explicitly.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>, tasks 4.1-4.8
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
