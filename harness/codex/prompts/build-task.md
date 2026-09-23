# build-task: implementation owned by a Codex worker

Copy this file per task, fill every placeholder, and delete the placeholder lines you do not
need. The contract it satisfies is in `../../codex-workers.md` under "The prompt contract".
A prompt that leaves scope implicit produces a confident wrong answer, because the worker does
not read `.cursor/rules/`.

## Outcome

<One observable result. Not a direction, not "improve X". Example: "catalogue search returns
only entries whose gate decision is PUBLISHABLE, and a query with no matches returns an empty
list rather than every entry".>

## Scope

Working root: the repository root.
Read first, in this order:
- `AGENTS.md` - the always-on contract, including the rights rules that bind you
- `openspec/changes/<change>/proposal.md`, `design.md`, `tasks.md` - this task's contract
- <the spec in `openspec/specs/**` that states the requirement>
- <the source files you will change>

Write only these files:
- <exact path>
- <exact path>

Nothing else. Do not add a file that is not listed.

## Hard rules

- Do not run git. Do not create, amend or push a commit.
- Do not touch a `.env` file, a credential, or anything under `.velmor/`.
- No `try/except`. It is forbidden in this repository unless the task explicitly authorizes a
  specific exception and names the class; see `.cursor/rules/03-error-handling.mdc`. If you
  believe one is required, reply `BLOCKED` with the reason instead of writing it.
- Preserve the rights contract: no model output becomes a verdict, nothing is publishable
  without `GateDecision.PUBLISHABLE`, every non-publishable decision keeps at least one
  reason, and a verdict is append-only.
- Do not edit anything under `packages/services/src/rights/` or
  `packages/services/src/screening/`. Those are a human-approved, Cursor-owned surface.
- Every buyer-visible string comes from the locale dictionaries. Never hardcode copy and never
  choose a language.
- Match the surrounding style. Do not refactor a neighbour, rename a symbol, or "clean up
  while here".
- No compatibility shim, re-export or transitional alias. Change every caller instead.

## Verification boundary

Run exactly these, from the repository root, and nothing else:

- `uv run ruff check`
- `uv run python -m pytest packages velmor -q`

Do not retry a failure. Run each once; if it fails, that is the result to report.
No network commands at all: no `uv sync`, no `pip`, no `docker`, no database, no `npm`.

## Budget

<token budget>. Reserve enough to run the two commands above and write the handoff. If the
work cannot be finished without dropping scope, reply exactly `CONTEXT_LIMIT` rather than
guessing or silently narrowing the task.

## Reply contract

On success: `DONE <comma-separated files changed>`
On failure: `BLOCKED <one-line reason>`
