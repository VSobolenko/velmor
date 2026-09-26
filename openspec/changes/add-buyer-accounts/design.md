## Context

See `proposal.md` for motivation. The constraints that shape the approach:

- **The identity is public and unverified today.** `storefront/src/lib/api/client.ts:59` reads the
  buyer from `process.env.NEXT_PUBLIC_BUYER_ID`, a build-time value compiled into the JavaScript every
  visitor downloads, and `packages/api/src/app.py:638-644` (`_require_buyer_id`) returns it from the
  `X-Buyer-Id` header with no verification. `storefront/.env.example` sets it to `demo-buyer`.
- **The order and entitlement records already carry an opaque `buyer_id`**
  (`Schema.orders.buyer_id`, `Schema.entitlements.buyer_id`, read by
  `packages/services/src/persistence/postgres.py`), and nothing else about them names a person. There
  is therefore no model to redesign: what has to change is where that string comes from.
- **The storefront and the API are separate origins** - `shop...sslip.io` to Next on `:3000` and
  `velmor-api...sslip.io` to the API on `:8080` (`.deploy/caddy-velmor-blocks.caddy`) - there is no
  path route between them, and the API sets `allow_credentials=False`
  (`packages/api/src/app.py:188`). The browser calls the API directly today.
- **The API already has the mechanisms this needs.** `SettingsLoader.required_*` is the only way a
  setting is read; `DELIVERY_GRANT_SECRET` with `DELIVERY_GRANT_LIFETIME_SECONDS`
  (`packages/api/src/configs/settings.py:35-39`) is a working precedent for a secret plus a lifetime;
  the operator refund key is compared with `hmac.compare_digest` (`app.py:636`).
- **The storefront is presentation only** - no rights logic, no payment secret, no privileged
  credential, and it never reaches the database (`.cursor/skills/storefront-ux/SKILL.md`).
- Constraints from the project: no dependency without approval, no new `try/except`, `check:i18n`
  enforces dictionary parity across the three locales, and the working environment is Windows.

## Goals / Non-Goals

**Goals:**

- One account per buyer, owned by the buyer, with the shop attributable to a person.
- A session cookie the browser sends first-party, so no third-party-cookie dependency and no
  `allow_credentials` exposure.
- The smallest possible change to the persistence of orders and entitlements: their owner becomes an
  account, without rewriting what an order is.
- No new dependency, and no new secret beyond the session lifetime.

**Non-Goals:**

- Email delivery of any kind (verification, reset, notification). No provider exists; see
  `proposal.md` - Non-goals.
- A server-side cart. The cart stays where it is and is preserved across the sign-in transition.
- Distributed or clustered sessions beyond what the shared database already provides.
- Any change to the rights engine, the publication gate, or a verdict.

## Decisions

### 1. The account is owned by Python, not by the storefront

Accounts, credentials and sessions are domain and persistence concerns in `packages/services`, and
the HTTP surface is in `packages/api`. This follows the fixed direction in
`.cursor/rules/02-architecture-layers.mdc`: `packages/services` imports `packages/core` and no agent,
and `packages/api` composes the services. The rights engine is not involved at all and its purity is
untouched.

Alternatives considered and rejected:

- **NextAuth / Auth.js in the storefront.** The orders and entitlements are Python-owned; the
  storefront would hold a second, divergent notion of who a buyer is, and it would have to reach the
  API with a privileged credential to act on their behalf, which the storefront is explicitly
  forbidden to hold.
- **Saleor customers.** Saleor is an integration used server-side by `velmor publish`; the storefront
  never speaks to it and holds no Saleor credential. The order and entitlement records that decide
  access live in our Postgres, so the account has to live beside them.
- **A signed token (JWT) issued by the API and verified by the storefront.** Not chosen; see
  decision 3.

### 2. Passwords are hashed with `hashlib.scrypt`, and no dependency is added

Each account stores a random per-user salt and `hashlib.scrypt(password, salt=..., n=2**14, r=8, p=1)`.
Verification recomputes and compares with `hmac.compare_digest`. Both are in the Python standard
library.

Alternatives considered and rejected:

- **`argon2-cffi` or `bcrypt`.** Each is a new dependency and a binary wheel, which needs explicit
  approval and buys a marginal improvement over scrypt for this threat model. The project's rule is
  that a dependency needs a stated reason; there is not a strong enough one here.
- **PBKDF2 via `hashlib.pbkdf2_hmac`.** Also stdlib and also acceptable, but scrypt is memory-hard,
  which is the property that matters against a GPU attacker, so scrypt is chosen.
- **Dependency and security note:** none is added. The only cryptographic choice is the standard
  library's scrypt with an explicit work factor, and the salt is per user and random
  (`secrets.token_bytes`).

### 3. A session is an opaque random token, stored hashed, and delivered in a first-party cookie

The session credential is `secrets.token_urlsafe(32)`. The database stores only `sha256(token)` beside
`user_id`, `created_at`, `expires_at` and `revoked_at`, so a database read does not yield a usable
credential. Signing in issues a new token; signing out and changing a password set `revoked_at`.
Expiry is `SESSION_LIFETIME_SECONDS` after issue. Nothing is stored in the token, so nothing needs
signing and no signing secret is introduced.

A plain SHA-256 is correct here rather than scrypt: the token is 256 bits of `secrets` output, so it
has no guessable structure and a slow hash would only add latency to every request.

Alternatives considered and rejected:

- **JWT signed with a secret.** Revocation before expiry needs a denylist, which is the database table
  this design already has; the signature would then be decoration. It also invites hand-rolled
  signing or a new library.
- **Sessions in Redis only.** Redis is in the stack and would work, but the session must survive a
  Redis restart to keep a buyer signed in, and the account data is already in Postgres. Redis is used
  for the rate limiter (decision 7), where loss is acceptable.

### 4. The API is reached under the storefront's own origin, so the cookie is first-party

`.deploy/caddy-velmor-blocks.caddy` gains a path route on the shop host, forwarding `/api/*` to
`host.docker.internal:8080`. The storefront's API base URL becomes a same-origin path, so the browser
sends the session cookie first-party with `SameSite=Lax` and no `allow_credentials` and no
cross-origin credential dance.

This is also what makes an entitlement download work: the download is a browser navigation, and
`storefront/src/lib/api/client.ts:201` records that a bare navigation cannot carry `X-Buyer-Id`. A
cookie on the same origin is sent on the navigation.

Alternatives considered and rejected:

- **Cookie issued by the API host, shared through the parent domain, with `SameSite=None`.** This is
  a third-party cookie in the browser's view, already blocked by default in current Chrome and Safari,
  and it forces `allow_credentials=True` plus a credentialed CORS origin. It would work in a demo and
  break for a real buyer.
- **The Next server holds the session and the browser never sees the API.** The strongest isolation,
  but every page currently fetches in the browser, so it is a rewrite of the whole data layer. It
  remains the right direction if the API ever needs to stop being publicly reachable; it is not this
  change.

### 5. `buyer_id` becomes the account id, and `X-Buyer-Id` is removed

`_require_buyer_id` resolves a session instead of reading a header, and the account id it returns is
the same opaque string the orders and entitlements already store. No table is rewritten and no record
is migrated.

This is the decisive simplification: the ownership contract exists, and only its source changes. It
also means a request that cannot present a session has no owner, and is refused rather than defaulted.

### 6. State-changing routes are POST or DELETE, and `SameSite=Lax` is the CSRF defence

`SameSite=Lax` permits the cookie on top-level navigations but not on a cross-site `POST`, and every
state change in this change is a `POST` or a `DELETE`. That is sufficient, so no CSRF token is added.

Accepted trade-off: a future state-changing `GET` would break this, and would require a token. Recorded
here so the next change does not quietly add one.

### 7. Rate limiting is counted in Postgres, on the account row

Failed sign-ins are counted against the account: `users.failed_attempts` and `users.last_failed_at`,
with a window after which the counter resets on its own. Once the count is reached within the window,
further attempts for that account are refused with a reason, and a successful sign-in resets the
counter. No separate table is needed, and there is nothing to keep in sync.

Alternatives considered and rejected:

- **Redis counters.** `redis>=8.1.0` is declared in `pyproject.toml`, so the dependency exists, but no
  client is wired anywhere in the source today. Using it would add a required service and a required
  `SettingsLoader` value, and by this repository's rule that a missing setting must raise at bootstrap,
  the API would refuse to start without a reachable Redis. The Redis in the deployed environment was
  not verified from here, so that is a deployment prerequisite this change would introduce silently.
  Postgres is already required by the API for every other read, so a database failure already fails the
  request and the limiter cannot fail open by accident.
- **An in-process counter.** Rejected under `.cursor/rules/02-architecture-layers.mdc`: a module-level
  dict standing in for a service is the shared mutable state that rule forbids, and it would reset on
  every restart and be wrong the moment a second process exists.
- **Trusting the proxy's rate limiting only.** Rejected: it is not in this repository, nothing verifies
  it, and an unverified gate is not a gate.

Accepted limitation, stated rather than hidden: counting per account cannot throttle a campaign spread
across many email addresses, because there is no account to count against. The identical refusal for a
wrong password and an unknown address still prevents account enumeration. A per-origin limit is what
would close that gap, and it needs a shared counter store, so it belongs with a Redis deployment.

### 8. The refusals are values, not exceptions

A refused registration, sign-in or password change is a typed outcome carrying a reason, in the shape
the rest of this repository already uses for a refusal (`GateDecision` with its reasons, the checkout's
`CheckoutRefusedError`). The HTTP layer turns a refusal into a response; nothing above it catches an
exception to find out whether a password matched. This keeps the account decision decidable from its
inputs, in the same spirit as the rights verdict, and it means no `try` is needed to express a refusal.
The one place a database conflict could tempt a catch - a duplicate email on registration - is handled
by `ON CONFLICT DO NOTHING` and a row count, not by an exception.

### 8. Framework choice: plain Python, and this is stated deliberately

Authentication is decidable from its inputs, has no branching that warrants a graph, and involves no
judgement, so it is plain Python per `.cursor/rules/05-agent-graphs.mdc`. No LangGraph node, no
Pydantic AI extraction, no model call, and no DeepAgents. An account decision is never made by a model,
and the same is true of the refusal reasons.

### 9. The minimum password length has one owner

The minimum is a single value owned by the API and surfaced to the sign-in and registration forms
through the API, and it is enforced in the API. The three dictionaries carry the wording, not the
number.

Rejected: writing the number into each dictionary, which is three sources that drift, and a
per-locale check to keep them aligned is a sensor that exists only because the first mistake was made.

### 10. The strings that describe the shared demo buyer are removed

`account.demoNote` and `checkout.buyerDemoNote` tell the buyer they are shopping as one shared
demonstration buyer. Once buying requires an account that sentence is false, so both keys are removed
from all three dictionaries in this change. Leaving them would be the surface lying about the model,
which is the defect class `.cursor/rules/07-product-surface.mdc` exists for.

## Buyer-facing surfaces

Each page follows `.cursor/skills/storefront-ux/SKILL.md`. That file's "Adding a page" procedure is the
pattern: copy keys into all three dictionaries first, compose from the design system, design every
state including `unauthenticated`, check 390 px before 1440 px, then run the parity check and the
build. Its "The design system" table is the component contract - labelled `Input`, `Button` with a
loading and disabled state and a stable width so a label change does not move the layout, `Card` as
the surface, `EmptyState` as a statement plus a way out, 44 px targets. Its "The visual checklist" is
the acceptance list, run at 390 px and 1440 px in each locale.

The skill has no dedicated authentication-form pattern, so none is invented: a credential form is a
`Card` holding labelled `Input`s and one primary `Button`, which is what the design-system contract
already describes. If a pattern beyond that turns out to be needed, it is researched and cited before
it is written, per the `design` rules in `openspec/config.yaml`.

| Page | Locale keys (new unless noted) | States | Image |
|---|---|---|---|
| `/[locale]/account/sign-in` | `nav.signIn`, `auth.signInTitle`, `auth.emailLabel`, `auth.passwordLabel`, `auth.signInAction`, `auth.toSignUp`, `auth.mismatch`, `auth.serviceUnavailable` | idle, submitting, refused credentials, service unavailable | none - no imagery is introduced |
| `/[locale]/account/sign-up` | `auth.signUpTitle`, `auth.displayNameLabel`, `auth.signUpAction`, `auth.toSignIn`, `auth.emailTaken`, `auth.passwordRule`, `auth.minimumLength` | idle, submitting, address already used, password below the minimum, service unavailable | none |
| `/[locale]/account/profile` | `account.profile`, `auth.emailLabel` (reused), `auth.displayNameLabel` (reused) | loading, loaded, unauthenticated, service unavailable | none |
| `/[locale]/account/password` | `account.changePassword`, `account.currentPassword`, `account.newPassword`, `auth.passwordRule`, `account.passwordChanged`, `account.wrongPassword` | idle, submitting, changed, wrong current password, new password below the minimum, unauthenticated | none |
| Account pages (existing) | existing `account.*` keys; the account is now gated | loading, empty, error, unauthenticated, not-found | unchanged - the existing layout is preserved |
| Header, every page | `nav.signIn`, `nav.account` (existing), `nav.signOut` | anonymous, signed in | unchanged |
| Checkout, anonymous | `checkout.signInRequired`, `checkout.signInCta` | anonymous, signed in | unchanged |

Removed keys: `account.demoNote`, `checkout.buyerDemoNote`.

## Risks / Trade-offs

- **[Removing `X-Buyer-Id` breaks every existing client and test that used it]** - Mitigation: the API
  tests and the deployment scripts are rewritten in the same change, and the header is removed rather
  than left accepted-but-ignored. A silently accepted header would be a second way to name an owner,
  which is the defect being removed.
- **[The storefront and the API must be reachable under one origin, which is a deployment change]** -
  Mitigation: the Caddy route lands with the change; the API host stays available so the B2B surface
  and existing probes keep working.
- **[A session cookie cannot be set for a bare `http://` development host]** - Mitigation: browsers
  treat `localhost` as a secure context, so `Secure` remains on and development is unaffected; the
  documented local run uses the loopback origin.
- **[The rate limiter fails closed, so a Redis outage refuses sign-in]** - Accepted, stated in
  decision 7.
- **[Sign-in and registration are the first pages an anonymous visitor meets, and a broken one blocks
  every purchase]** - Mitigation: the states in the table above are part of the spec, and `/ux-verify`
  is run over the running shop in all three locales, with screenshots as the evidence.
- **[A session is a bearer credential, and the cookie is the only thing protecting it]** -
  Mitigation: `HttpOnly`, `Secure`, `SameSite=Lax`, an expiry, rotation on sign-in, revocation on
  sign-out and on password change, and only a hash stored server-side.
- **[No email verification means an account can be registered with an address its owner does not
  control]** - Accepted and stated in the proposal's non-goals. It is a real limitation, and the
  remedy (an email provider) is a separate change rather than a stub here.
- **[No password reset means a forgotten password locks a buyer out]** - Accepted, same as above, and
  the honest consequence of having no way to send mail.

## Migration Plan

1. The new tables are additive (`users`, `sessions`); nothing existing is altered, and no backfill is
   required, because the demo rows keep the `demo-buyer` value they have (see `proposal.md` -
   Non-goals).
2. The API ships with the session resolution and without `X-Buyer-Id` acceptance, and the storefront
   ships with the same-origin base URL, in one release: a storefront that sends a header to an API
   that no longer reads it would show every buyer an empty account.
3. The Caddy path route is added before the storefront build that depends on it.
4. Rollback: revert the storefront and the API together and drop the route. The `users` and `sessions`
   tables are unused by the previous revision, so leaving them in place is safe and keeps any account
   that was created.

## Open Questions

- Whether the cart should later move to the account so it follows a buyer across devices. It changes
  no requirement in this change and no task, and it is deferred deliberately: the chosen scope keeps
  the cart where it is and only requires that it survive the sign-in transition.
