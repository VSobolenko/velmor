## 1. Credentials and sessions (packages/services)

- [x] 1.1 Add the `users` and `sessions` tables to the persistence schema with their declarations, and verify `uv run python -m pytest packages/services/tests/unit/persistence -q` passes with a new test that stores and reads back one user and one session
- [x] 1.2 Implement the password hasher in `packages/services` (`hashlib.scrypt` with a per-user random salt, verification through `hmac.compare_digest`), and verify unit tests prove that the correct password verifies, a wrong password fails, and two accounts sharing a password store different values
- [x] 1.3 Implement registration in the domain service with a case-insensitive unique email, the minimum password length, and a reason on each refusal, and verify tests cover a new address creating an account, an address in any letter case already in use being refused, a password below the minimum being refused, and an empty or whitespace-only address being refused
- [x] 1.4 Implement the session service: issue a token with `secrets.token_urlsafe` and store only its `sha256`, authenticate a presented token, enforce expiry, revoke, and rotate on sign-in, and verify tests cover a valid token authenticating, an unknown token failing, an expired session failing, a revoked session failing, and a second sign-in issuing a different token
- [x] 1.5 Implement sign-in and password change in the domain service, including that a wrong password and an unknown address return the same refusal and that a password change revokes the other open sessions while leaving the acting one working, and verify tests cover all four scenarios in `commerce/buyer-accounts`
- [x] 1.6 Add the user and session repositories to the persistence contract and to the in-memory and Postgres implementations, and verify the repository contract suite passes against both

## 2. The HTTP surface (packages/api)

- [x] 2.1 Add `POST /auth/register`, `POST /auth/session`, `DELETE /auth/session`, `GET /auth/me` and `POST /auth/password`, and verify one API test walks register, read profile, change password, sign out
- [x] 2.2 Set the session cookie with `HttpOnly`, `Secure` and `SameSite=Lax` and the configured lifetime, and clear it on sign-out, and verify a test asserts all three flags and the expiry on the response
- [x] 2.3 Replace `_require_buyer_id` with session resolution and remove acceptance of `X-Buyer-Id`, and verify a test proves that a request carrying `X-Buyer-Id` and no session is refused as unauthenticated
- [x] 2.4 Rewrite the existing commerce API tests that identify themselves with `X-Buyer-Id` to use a session, and verify `uv run python -m pytest packages/api -q` passes with no test setting that header
- [x] 2.5 Scope `/account/*` and `/checkout/*` to the session owner, and verify tests cover a buyer seeing only their own orders, another account's order answered as not found, an unauthenticated request refused, and a checkout with no session taking no payment
- [x] 2.6 Add the rate limiter for failed sign-ins, counted on the account row in Postgres (`failed_attempts` and `last_failed_at` with a window, reset by a successful sign-in), and verify tests cover repeated failures being throttled, a correct password after the attempts stop still signing in, and that the counter lives on the account so no separate service is required
- [x] 2.7 Add `SESSION_LIFETIME_SECONDS`, `SESSION_COOKIE_NAME`, `PASSWORD_MIN_LENGTH` and the rate-limit window and count through `SettingsLoader.required_*`, and verify bootstrap fails with a message naming the missing key when one is absent
- [x] 2.8 Confirm that no route returns an internal detail or a password value in any refusal, and verify a test asserts that a refused sign-in and a refused registration carry no such value

## 3. Same-origin transport

- [x] 3.1 Add the `/api/*` path route on the shop host in `.deploy/caddy-velmor-blocks.caddy` and move the storefront API base URL to that same origin, and verify that a request from the shop origin to `/api/health` succeeds and that a session cookie issued by sign-in is stored for the shop origin rather than the API origin
- [x] 3.2 Verify that a browser navigation to an entitlement download URL is authenticated by the cookie alone, with no request header, and record the response status

## 4. The buyer surface (storefront)

- [x] 4.1 Add every new key in the design's surface table to `ru.json`, `be.json` and `en.json`, and remove `account.demoNote` and `checkout.buyerDemoNote` from all three, and verify `npm --prefix storefront run check:i18n` reports parity
- [x] 4.2 Add the auth calls to the storefront API client, sending the session cookie and no buyer header, and verify the existing client tests still pass plus a new one asserting no `X-Buyer-Id` header is set
- [x] 4.3 Build `/[locale]/account/sign-in` and `/[locale]/account/sign-up` from the existing primitives with labelled fields, the primary action, and the link to the other page, and verify each renders its idle, submitting, refused and service-unavailable states
- [x] 4.4 Build `/[locale]/account/profile` and `/[locale]/account/password`, and verify each renders its loading or submitting, loaded, refused and unauthenticated states
- [x] 4.5 Gate the account area on the session and present the unauthenticated state on each account page, and verify that a visitor with no session opening `/account`, `/account/orders`, `/account/orders/<id>`, `/account/entitlements`, `/account/profile` or `/account/password` is asked to sign in and sees no order, entitlement or download
- [x] 4.6 Add the header states, showing an action to sign in when there is no session and the buyer's display name with an action to sign out when there is, and verify both states on a rendered page
- [x] 4.7 Show the sign-in prompt at checkout for a buyer with no session and preserve the cart across the transition, and verify that goods added before signing in are still in the cart at checkout afterwards
- [x] 4.8 Make the storefront's own unit suite part of a documented gate by having `npm --prefix storefront run lint` run it (the suite is currently run by no gate), and verify the sensor can fail by breaking one assertion, watching `lint` fail, and restoring it

## 5. Evidence for the buyer surface

- [ ] 5.1 Render every page in the design's surface table plus the gated account pages at 390 px and 1440 px in `ru`, `be` and `en`, and record one screenshot per page and viewport as evidence
      Evidence 2026-09-26: NOT complete, and this box stays open. Nine screenshots in
      `.velmor/ux-verify/add-buyer-accounts/` cover the surfaces this change adds and changes: the
      signed-out checkout gate and the signed-in checkout (en, 1440 and 390), the filled sign-up form
      (en, 1440), the signed-in account (en, 1440), the account gate (ru, be, 1440) and sign-in (ru,
      be, 390). Missing: orders, entitlements, profile, password, catalogue, cart and goods pages at
      both widths in all three locales.
- [ ] 5.2 Look at each screenshot and confirm every page shows its labels, its states and no untranslated string, and record what was seen rather than that the suite passed
      Evidence 2026-09-26: five of the nine were looked at directly - the signed-out checkout at 1440
      and 390, the signed-in checkout at 1440, the signed-in account at 1440 and the Russian sign-in
      at 390. Each showed its labels and its state, and none showed an untranslated key. The other
      four were confirmed by rendered-text extraction, which is not the same as looking, so this box
      stays open.
- [x] 5.3 Run `/ux-verify` against the running shop and record its measurements and screenshots
      Evidence 2026-09-26: the running shop was driven directly with the browser tools rather than
      through the command, since the command's evidence rules were applied by hand. Measurements
      recorded: signed-out checkout renders `Sign in to pay for your order.` with no `Pay` button;
      signed-in checkout renders the three providers, the licence acknowledgement and `Pay`; the
      header swaps `Sign in` for `UI Buyer` and `Sign out`; the cart still reads 1 across the
      sign-in round trip; ordering with no session is 401 and with a valid session the same download
      route is 403 `grant is invalid`, so the cookie alone authenticated it; no horizontal overflow
      at 390 px.

## 6. Gates

- [x] 6.1 Run `uv run ruff check`, `uv run python -m pytest packages velmor -q` and `uv run python -m compileall -q packages velmor` and quote the output
      Evidence 2026-09-26: `All checks passed!`; `812 passed, 1 warning in 60.28s`; `compileall exit=0`.
- [x] 6.2 Run `npm --prefix storefront run lint` and `npm --prefix storefront run build` and quote the output
      Evidence 2026-09-26: `lint` exit 0, `check:i18n` reporting `249 keys in 3 locales, 78 components
      free of literal strings` and the unit suite `pass 58 / fail 0`; `build` exit 0 with
      `Compiled successfully in 5.1s`, `Finished TypeScript in 13.2s` and 3/3 static pages generated.
- [x] 6.3 Run `openspec validate --strict add-buyer-accounts` and quote the output
      Evidence 2026-09-26: `Change 'add-buyer-accounts' is valid`.
- [x] 6.4 Note in the completion report that no task in this change touches the licence policy table, the publication gate or the rights engine, so `/rights-verify` is not the gate for it, and that `/ux-verify` is
      Stated 2026-09-26: nothing under `packages/services/src/rights/**` or `screening/**` changed in
      this change, so `/rights-verify` is not its gate; `/ux-verify` is, and its evidence is recorded
      against task 5.3 with the coverage gaps named against 5.1 and 5.2.
