# Codex worker prompts

One file per worker, one worker per id. The runner reads the file and pipes it to Codex on
stdin:

```bash
node scripts/codex-run.mjs run --id <id> --prompt-file harness/codex/prompts/<file>.md
```

Prompts live here, in the repository, on purpose. The worker ledger lives in `.velmor/codex/`
and is git-ignored, but `.velmor/` is in `.cursorignore`, so Cursor denies an agent both read
and write on it: a prompt stored there could not be written by the agent that has to write it.
A prompt here is also the task statement a reviewer needs in order to judge a worker's diff,
which is the whole reason the diff can be trusted.

The contract that a prompt must satisfy is in `../../codex-workers.md` under "The prompt
contract". Copy the template below rather than writing from memory.

```markdown
# <id>: <one observable outcome>

## Outcome
<One observable result. Not a direction, not "improve X">

## Scope
Working root: <the exact directory>.
Read: <the exact files and specs>.
Write: <the exact files you may change. Nothing else>

## Inputs
Read these before deciding anything:
- <spec, AGENTS.md section, source file>

## Hard rules
- Do not run git. Do not touch secrets or `.env` files.
- No `try/except` unless this prompt explicitly authorizes it (see `.cursor/rules/03-error-handling.mdc`).
- Preserve the rights contract: nothing is publishable without a PUBLISHABLE gate decision,
  and a non-PUBLISHABLE decision keeps its reasons.
- Keep every buyer-visible string in the locale dictionaries.
- Do not edit a file outside the list above. Do not refactor neighbours.

## Verification boundary
Run only these, and do not retry a failure:
- `uv run ruff check`
- `uv run python -m pytest packages velmor -q`

No network commands: no `uv sync`, no `docker`, no `pip`, no database.

## Budget
<token budget>. Reserve enough to verify and hand off. If the work cannot finish without
dropping scope, reply exactly `CONTEXT_LIMIT` rather than guessing.

## Reply contract
On success: `DONE <comma-separated files>`
On failure: `BLOCKED <one-line reason>`
```

`smoke-test.md` is a read-only prompt that proves the channel works end to end. Run it after
a change to the launcher, the runner or the Codex CLI itself:

```bash
node scripts/codex-run.mjs run --id smoke --prompt-file harness/codex/prompts/smoke-test.md \
  --sandbox read-only --effort low --label 'Channel smoke test'
node scripts/codex-run.mjs status
```
