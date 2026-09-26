# Build: buyer accounts, part 1 - credentials, sessions and the HTTP surface

Implement tasks 1.1 to 1.6 and 2.1 to 2.8 of `openspec/changes/add-buyer-accounts/tasks.md`. Do not
edit `tasks.md`; the orchestrator marks it after verifying your work.

## Read first, in this order

- `AGENTS.md` - the always-on contract, and it binds you.
- `openspec/changes/add-buyer-accounts/proposal.md` - why, and the non-goals. The non-goals are part
  of the task: anything listed there must NOT be built.
- `openspec/changes/add-buyer-accounts/specs/commerce/buyer-accounts/spec.md` - the behaviour you are
  implementing, requirement by requirement.
- `openspec/changes/add-buyer-accounts/design.md` - how. Decisions 1 to 8 are binding.
- `packages/api/src/app.py` - the HTTP surface. `_require_buyer_id` (line 638) is what you are
  replacing, and it is called from six handlers: lines 401, 427, 452, 462, 472, 519.
- `velmor/api_server.py` line 127 - where `ApiApplication` is constructed in production. You must add
  your new services as keyword arguments here.
- `packages/api/tests/unit/test_commerce_api.py` line 200 - where `ApiApplication` is constructed in
  the tests. You must add the same arguments here, or every API test fails to collect.
- `packages/api/src/configs/settings.py` - how a setting is read.
- `packages/services/src/persistence/schema.py`, `contract.py`, `memory.py`, `postgres.py` - the
  persistence conventions you are extending.
- `.cursor/rules/02-architecture-layers.mdc` and `.cursor/rules/03-error-handling.mdc` - the import
  direction, and why a `try` needs authorization you do not have here.

## What to build

Follow the design. The load-bearing decisions, restated because getting them wrong invalidates the work:

1. **The account id IS the `buyer_id` already stored on orders and entitlements.** Do not rename the
   column, do not add a mapping table, do not migrate a record. `_require_buyer_id` changes from
   reading a header to resolving a session, and returns the account id.
2. **`X-Buyer-Id` is removed, not deprecated.** No route may read it. A request that cannot present a
   valid session has no owner and is refused. Do not leave it accepted-and-ignored.
3. **Passwords: `hashlib.scrypt` with a per-user random salt** (`secrets.token_bytes`), verified with
   `hmac.compare_digest`. No new dependency, and no `passlib`/`bcrypt`/`argon2`.
4. **Sessions: the token is `secrets.token_urlsafe(32)`; the database stores only `sha256(token)`**
   beside `user_id`, `created_at`, `expires_at`, `revoked_at`. Plain SHA-256 is correct here and is
   deliberate: the token is 256 bits of `secrets` output, so there is nothing to slow down.
5. **The cookie is `HttpOnly`, `Secure`, `SameSite=Lax`**, with the configured lifetime. State-changing
   routes are `POST` or `DELETE`, which is what makes `Lax` sufficient; do not add a CSRF token.
6. **Rate limiting is counted on the account row, in Postgres** - `failed_attempts` and `last_failed_at`
   with a window. NOT Redis. `redis>=8.1.0` is declared in `pyproject.toml` but no client is wired in
   the source, and making Redis required would make the API refuse to start without it.
7. **A refusal is a value, not an exception.** Registration, sign-in and password change return a typed
   outcome carrying a reason. Do not signal a refusal by raising.
8. **The minimum password length has exactly one owner:** a setting read through `SettingsLoader`, and
   the API enforces it. Do not write the number into any locale dictionary.

Settings come from `SettingsLoader`, which offers only `required_str`, `required_int`, `required_bool`,
`required_path`, `required_secret` and `required_str_list`. There is no optional accessor and you must
not add one.

### No `try`, and how to avoid the one you might reach for

`.cursor/rules/03-error-handling.mdc` forbids `try/except` unless it is explicitly authorized. You are
not authorized to add one. In particular, do not wrap the database to catch a duplicate-email race.
Register with `INSERT ... ON CONFLICT DO NOTHING` (`sqlalchemy.dialects.postgresql.insert(...)
.on_conflict_do_nothing(index_elements=['email'])`) and treat a row count of zero as "this address is
already in use". A database error that is not a unique violation is a real failure and must propagate.

### Layout

- `packages/services/src/domain/account.py` - the `Account` and `Session` models. Fields only, no
  behaviour, no `@field_validator`, no `model_post_init`.
- `packages/services/src/auth/password.py`, `sessions.py`, `service.py` - the password hasher, the
  session service and the account service. Class methods, no module-level functions.
- The refusal values, in the domain, named to fit the existing naming there.
- Extend `packages/services/src/persistence/schema.py` with the `users` and `sessions` tables, and add
  the repositories to `contract.py`, `memory.py` and `postgres.py`.
- Add the routes to `packages/api/src/app.py`, the settings to `packages/api/src/configs/settings.py`
  and the new variable names with placeholder values to `packages/api/.env.example`.
- Wire the new services in `velmor/api_server.py` and in the test factory at
  `packages/api/tests/unit/test_commerce_api.py:200`.

Email addresses are compared case-insensitively with surrounding whitespace ignored. Normalise the
value where it enters the domain and store the normalised form, so the unique index is the contract.

## Constraints that will fail the work

- Do not add any dependency. `hashlib`, `hmac`, `secrets`, `sqlalchemy` and `pydantic` are enough.
- Do not edit `packages/services/src/rights/**` or `packages/services/src/screening/**`. Nothing in this
  change touches the verdict path, and a change there would need a human.
- Do not edit `harness/**`, `.cursor/**`, `scripts/**`, `.deploy/**`, `storefront/**` or anything under
  `openspec/**`. The storefront is a separate task.
- Every setting is required: read it with `SettingsLoader.required_*`, never with a default. A missing
  value must raise at bootstrap naming the key.
- `ruff` runs with `line-length = 100` and single quotes. Do not add a rule to
  `[tool.ruff.lint].select`.
- No `TODO`, no compatibility shim, no re-export, no transitional alias.
- Nothing may return a password value or an internal detail in any refusal.

## Tests

Write the tests as part of the task that adds the behaviour, not at the end. Cover, at minimum, every
scenario in `specs/commerce/buyer-accounts/spec.md` that concerns this part, and these specifically:

- The stored value is not the password, and two accounts sharing a password store different values.
- A wrong password and an unknown address are refused identically.
- An expired session, a revoked session and a token that was never issued each grant nothing.
- Signing in again issues a different credential.
- A password change revokes the other open sessions and leaves the acting one working.
- A request carrying `X-Buyer-Id` and no session is refused as unauthenticated.
- A signed-in buyer sees only their own orders; another account's order is answered as not found.
- A checkout with no session creates no order and takes no payment.
- A good that is not saleable is refused for a signed-in buyer exactly as for anyone else.

The existing API tests that identify themselves with `X-Buyer-Id` must be rewritten to sign in instead.
A test that still sets that header is a test that no longer describes the system.

## Verification boundary

Run exactly these and quote the last lines of each in your reply:

```
uv run ruff check
uv run python -m pytest packages -q
uv run python -m compileall -q packages velmor
```

`uv run python -m pytest packages -q` must pass with no failure. Do not retry a failing command: if one
fails, stop and report it. Do not run anything that needs the network, and do not run the storefront.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>, tasks 1.1-1.6 and 2.1-2.8
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
