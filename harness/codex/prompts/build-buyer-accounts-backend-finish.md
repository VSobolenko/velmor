# Finish: buyer accounts, part 1 - persistence, HTTP surface, wiring, tests

A previous worker built roughly the first three quarters of tasks 1.1-1.6 and 2.1-2.8 of
`openspec/changes/add-buyer-accounts/tasks.md` and then stopped part-way through the persistence work. Your
job is to finish it, and to correct three things in what is already there. Do not edit `tasks.md`.

## Read this before you run anything

**The shell in this environment is slow and it is what killed the previous worker.** Measured on the
previous run: `git status --short` took 34.9 seconds, `git diff --numstat` took 47.8 seconds, and one
command was killed at the tool limit of 22.8 seconds. The worker ran out of budget on shell round-trips,
not on the problem.

So, for this task:

- **Do not run any `git` command.** Not `status`, not `diff`, not `log`.
- **Do not run any exploratory shell command.** No `ls`, no `find`, no `cat`, no `grep`. Use the file
  reader and the search tool instead.
- **Run exactly three shell commands in the whole task**, the three verification commands at the end.
- Plan before writing, and batch your edits.

A single misplaced `git diff` costs more time here than the code does.

## What already exists and must be kept

Read these; they are the foundation, and they are broadly correct.

- `packages/services/src/domain/account.py` - `Account`, `Session`, `AccountOutcome`.
- `packages/services/src/auth/password.py` - `PasswordHasher` (scrypt, per-user salt,
  `hmac.compare_digest`).
- `packages/services/src/auth/sessions.py` - `SessionService` (`secrets.token_urlsafe(32)`, only the
  SHA-256 of the token is stored).
- `packages/services/src/auth/service.py` - `AccountService`.
- `packages/services/src/persistence/contract.py` - `AccountRepository`, `SessionRepository`.
- `packages/services/src/persistence/memory.py` - both repositories, on `InMemoryStore`.
- `packages/services/src/persistence/schema.py` - the `users` and `sessions` tables.

## Three corrections to what exists

1. **A refusal must be a stable code, never a prose sentence.**
   `AccountService` currently returns reasons like `'password must contain at least 10 characters'` and
   `'invalid credentials'`. A buyer-facing surface has to write that copy in the buyer's language, and
   it cannot translate a sentence the API assembled. Return codes instead, in the upper-case class
   constants the class already uses for them, e.g. `INVALID_CREDENTIALS = 'invalid_credentials'`,
   `EMAIL_UNAVAILABLE = 'email_unavailable'`, `PASSWORD_TOO_SHORT = 'password_too_short'`,
   `RATE_LIMITED = 'rate_limited'`, `CURRENT_PASSWORD_INCORRECT = 'current_password_incorrect'`,
   `EMAIL_REQUIRED = 'email_required'`. The minimum length stays a setting and the API reports it as its
   own field in a refusal body when the code is `PASSWORD_TOO_SHORT`; it must not be baked into a code
   or a sentence.
2. **`SessionService` must expose its token hash publicly.** `AccountService` currently calls
   `self._session_service._hash(token)`. Rename it to a public `hash_token` and call it by that name.
3. **The two persistence shapes must not disagree.** The `users` table carries the account as JSONB and
   also carries `failed_attempts` and `last_failed_at` as columns. Read the neighbouring tables in
   `schema.py` first and match the convention the repository already uses; if the JSONB payload is the
   stored model, then either write every scalar column from that model in one statement or drop the
   duplicated scalar columns. A column and a JSONB field that can drift is two sources of truth for one
   fact, and the rate limiter reads one of them.

## What is missing and must be built

1. **`packages/services/src/persistence/postgres.py`** - `AccountRepository` and `SessionRepository` on
   `PostgresStore`, following the existing methods in that file exactly. Registration must use
   `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing(index_elements=['email'])` and
   return whether a row was written. **Do not use `try/except`** to catch a unique violation;
   `.cursor/rules/03-error-handling.mdc` forbids it and a conflict is not an error here.
2. **`packages/api/src/app.py`** - the routes and the session resolution:
   - `POST /auth/register` `{ email, password, display_name }` creates the account, signs the buyer in,
     and returns the profile.
   - `POST /auth/session` `{ email, password }` signs in and returns the profile.
   - `DELETE /auth/session` signs out and clears the cookie.
   - `GET /auth/me` returns the signed-in buyer's profile.
   - `POST /auth/password` `{ current_password, new_password }` changes it and revokes the other
     sessions of that account, leaving the acting one valid.
   - The profile shape is `{ id, email, display_name }`. **No response may carry `password_hash`,
     `password_salt`, a token, or a session's `token_hash`.**
   - `_require_buyer_id` (line 638) is replaced by a dependency that resolves the account from the
     session cookie. It is called from six handlers: lines 401, 427, 452, 462, 472, 519. All six change.
     `X-Buyer-Id` is removed, not accepted-and-ignored.
   - The cookie is set with `httponly=True`, `secure=True`, `samesite='lax'`, `path='/'` and the
     configured lifetime, and its name comes from a setting.
3. **`packages/api/src/configs/settings.py`** - the new settings, each read through
   `SettingsLoader.required_*`: the session cookie name, the session lifetime in seconds, the minimum
   password length, the failed-attempt limit and the failed-attempt window in seconds.
4. **`packages/api/.env.example`** - the same names with placeholder values, committed as always.
5. **`velmor/api_server.py`** (line 127, where `ApiApplication` is constructed) - pass the new services
   as keyword arguments. Also pass them in the test factory at
   `packages/api/tests/unit/test_commerce_api.py` line 200, or every API test fails to collect.
6. **Tests** - cover every scenario in `specs/commerce/buyer-accounts/spec.md` that concerns this part,
   and specifically: the stored value is not the password and two accounts sharing a password store
   different values; a wrong password and an unknown address are refused identically; an expired, a
   revoked and a never-issued token each grant nothing; signing in again issues a different credential;
   a password change revokes the other sessions and leaves the acting one working; a request carrying
   `X-Buyer-Id` and no session is refused as unauthenticated; a signed-in buyer sees only their own
   orders and another account's order is answered as not found; a checkout with no session creates no
   order and takes no payment; a good that is not saleable is refused for a signed-in buyer exactly as
   for anyone else. Rewrite the existing tests that identify themselves with `X-Buyer-Id` to sign in
   instead - a test still setting that header no longer describes the system.

## Constraints

- No new dependency. `hashlib`, `hmac`, `secrets`, `sqlalchemy`, `pydantic` are enough.
- Do not touch `packages/services/src/rights/**` or `packages/services/src/screening/**`.
- Do not touch `harness/**`, `.cursor/**`, `scripts/**`, `.deploy/**`, `storefront/**` or `openspec/**`.
- No `try/except` anywhere. `raise` on malformed input rather than coercing a default.
- Every setting is required, read with `SettingsLoader.required_*`. A missing value raises at bootstrap
  naming the key.
- `ruff`: `line-length = 100`, single quotes. Do not add a lint rule.
- No `TODO`, no shim, no re-export, no alias.

## Verification boundary

Run exactly these three, and quote the last lines of each:

```
uv run ruff check
uv run python -m pytest packages -q
uv run python -m compileall -q packages velmor
```

`pytest` must pass with no failure. If a command fails, stop and report it; do not retry.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>, tasks 1.1-1.6 and 2.1-2.8
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
