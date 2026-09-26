## Why

The shop has no accounts, and the identity it does have is public. `storefront/src/lib/api/client.ts`
reads the buyer from `process.env.NEXT_PUBLIC_BUYER_ID` - a build-time value compiled into the
JavaScript every visitor downloads - and `packages/api/src/app.py:638-644` (`_require_buyer_id`)
trusts the `X-Buyer-Id` request header without verifying anything. Two consequences follow, and both
are live today:

- Every visitor to the deployed shop is the same buyer (`NEXT_PUBLIC_BUYER_ID=demo-buyer`): one cart,
  one purchase history, one set of download grants shared by all of them.
- Anyone can send another buyer's id in that header and read their orders and entitlement grants.

There is also no account to sign in to, so a buyer cannot keep a purchase history, and the shop
cannot tell two buyers apart. This change gives a buyer an account they own, and makes the order and
entitlement records that already carry a `buyer_id` point at that account instead of at a value the
client chose for itself.

## What Changes

- A buyer can register with an email address and a password, sign in, sign out, and change their
  password.
- A session is an opaque random token, stored only as a hash, delivered in an `HttpOnly`, `Secure`,
  `SameSite=Lax` cookie. It expires, and signing in rotates it. Revocation is the deletion of the
  session row, so no token library and no new dependency are introduced.
- Passwords are hashed with `hashlib.scrypt` (Python standard library) using a per-user salt, and
  verified with `hmac.compare_digest`. No password dependency is added.
- **BREAKING**: `X-Buyer-Id` is removed as a way to name a buyer. `/account/*` and `/checkout/*`
  derive the owner from the session; a request with no valid session is refused. Existing API tests
  that identify themselves with that header are rewritten against a session.
- The browser reaches the API under the storefront's own origin (`shop.../api/*` forwarded to the
  API), so the session cookie is first-party. This also fixes downloads: a browser navigation to the
  download URL carries the cookie, which a header could not do
  (`storefront/src/lib/api/client.ts:201`).
- Signing in is required to buy and to use the account. The catalogue and the cart stay open to
  everyone.
- The account gains pages the buyer can see, in all three locales, described under "What the buyer
  will see".

Non-goals:

- **No email is sent.** There is no email provider in this project, so password reset and email
  verification are impossible today. They are not stubbed and not faked; they are absent, and
  accounts are created without verification. Adding an email provider is a separate change.
- No social or OAuth sign-in, no two-factor authentication.
- No guest checkout: an anonymous visitor cannot complete a purchase.
- No account deletion, and no data export. The scope chosen is the account core.
- No staff, operator or admin role. The operator refund key
  (`packages/api/src/configs/settings.py`) is unchanged.
- No migration or claiming of the existing `demo-buyer` orders and entitlements. Real accounts start
  empty, and the demo rows stay where they are.
- Nothing about rights. No licence action, evidence rule, `GateDecision` or screening outcome changes.
  The purchase-time re-verification of the gate outcome is untouched.

## Capabilities

### New Capabilities

- `commerce/buyer-accounts`: registration, sign-in, sign-out, session lifetime and rotation, the
  buyer's profile and password change, and the rule that an order and an entitlement belong to an
  account and are readable only by it.

### Modified Capabilities

- `commerce/checkout-payment`: the owner of an order is the signed-in account, not a
  client-supplied header; a checkout started without a valid session is refused, and the gate
  re-verification at payment time is unchanged.
- `commerce/storefront`: the shop presents sign-in and sign-up, the account area is reachable only
  with a session, and the header shows the signed-in buyer rather than always linking to an open
  account page.

## Impact

- `packages/api`: new `/auth/*` routes, session-based buyer derivation replacing
  `_require_buyer_id`, CORS and cookie settings.
- `packages/services`: `users` and `sessions` tables in the persistence schema and their repositories;
  a password hasher and a session service. Both are pure and testable, and neither imports an agent
  framework.
- `packages/core`: a session signing/expiry setting read through `SettingsLoader.required_*`, in the
  same shape as the existing `DELIVERY_GRANT_SECRET` and `DELIVERY_GRANT_LIFETIME_SECONDS`.
- `storefront`: sign-in and sign-up pages, an authenticated account area, header states, and the API
  base URL moving to the same origin.
- Deployment: a Caddy path route forwarding `shop.../api/*` to the API, and new environment
  variables on the API host.
- Tests: the API commerce tests that use `X-Buyer-Id` are rewritten; new unit tests cover password
  hashing and verification, session issue/expiry/revocation, and the refusal of an unauthenticated
  account or checkout request.
- Dependencies: none added. `hashlib.scrypt`, `hmac`, `secrets` and the existing `cryptography` are
  sufficient.
- Verdicts: no verdict can change. `RightsResolver.ENGINE_VERSION` is not bumped, and the publication
  gate and its refusals are unchanged.

## What the buyer will see

All of the following ship in this change, in `en`, `ru` and `be`, with every string in the locale
dictionaries and the language chosen by the URL, never by the buyer's account:

- A sign-in page and a sign-up page, each a single card with labelled fields, the primary action, and
  a link to the other one.
- The header in its anonymous state shows a "Sign in" action; in its signed-in state it shows the
  buyer's display name and a "Sign out" action. The account link is no longer offered to a visitor
  with no session.
- An account area reachable only when signed in: account overview, order history, order detail, and
  entitlements with their downloads. These pages already exist and keep their current layout; what
  changes is that they require a session and name the signed-in buyer.
- A profile page where the buyer sees their email and display name, and a change-password form.
- On checkout, an anonymous buyer is shown a sign-in prompt with a link back to checkout. The cart is
  preserved across sign-in, so nothing they put in it is lost.
- Every new page renders the loading, empty, error and not-found states the shop already uses, and
  none of them shows a raw error or an untranslated string.

No new imagery is introduced: these are forms and lists, and they reuse the existing card, field,
button and empty-state components.
