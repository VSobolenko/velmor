# Peer protocol: Cursor and Codex

Cursor owns orchestration and final verification. Codex runs a different model family, so
its blind spots are uncorrelated with ours - that is the reason to use it, not the raw
model strength. A worker result is input to verification, never proof of completion.

## Codex is the default implementer, and that is enforced

Codex is not a peer you may consult when it suits. Product code under `packages/`, `velmor/`
and `storefront/` is written by a Codex worker; Cursor verifies it. The reason is structural:
Cursor verifies independently only if it did not write the thing it is checking. An agent that
authors the code and then grades it has one set of blind spots, and every subsequent check it
runs inherits them.

`.cursor/hooks/codex-gate.cjs` refuses a write to product code when the worker ledger holds no
worker for the current session, so this is a constraint rather than an instruction. Escape with
`VELMOR_CODEX_GATE=off` only for a documented exception - a one-line fix, the verdict path, or a
machine with no Codex - and say that you used it.

Never handed to Codex, at any rung of the ladder: `packages/services/src/rights/**`,
`packages/services/src/screening/**` (a human approves those; `policy-guard.cjs` asks for the
local write and the gate stands aside), and the harness itself - `.cursor/**`, `harness/**`,
`scripts/**`, `AGENTS.md`. An agent able to hand its own constraints to another agent can
relax them.

The gate cannot see Codex's writes; hooks intercept Cursor tool calls only. So the orchestrator
reviews the diff and runs, by hand, the gate the hook would have run. For `storefront/**` that
means the locale parity check, and `/ux-verify` before the work is called done.

## Role cards

Roles are assigned per task, not permanently. One agent may hold two on a small task.

| Role | Responsibility | Handoff |
|------|----------------|---------|
| **Build** | Python under `packages/` and `velmor/`, tests, wiring | Files changed, commands run with output, exact blockers |
| **Surface** | Storefront, locale dictionaries, buyer routes under `packages/api/` | What a buyer sees, and the screenshot paths |
| **Verify** | Read-only diff review, requirement challenges, evidence | Evidence and a PASS / FAIL / BLOCKED verdict |
| **Adjudicate** | Resolve a Build / Surface / Verify disagreement against the contract | Ruling, evidence, what it costs if the ruling is wrong, next owner |

Cursor normally orchestrates and verifies; it may take any role when needed. A Verify worker
runs `--sandbox read-only`. Two writers on the same files is a defect waiting to happen: put
them in separate worktrees, or give them disjoint file lists.

## What a peer may never do

These are not preferences, and a peer that does one is rejected and corrected, not debated:

- Weak `PublicationGate`, or remove a condition from it.
- Widen `LicenseMatrix.ALIASES` so an unrecognised string resolves.
- Let a model produce a `RightsVerdict`. A model contributes `Evidence`; it never decides.
- Wrap the gate or a rights call in `try/except`, or add a `try` anywhere without an
  explicit human authorisation for that catch in the current task.
- Edit `packages/services/src/rights/**` or `packages/services/src/screening/**` at all
  without an explicit human request. `policy-guard.cjs` guards the local writes; a Codex
  write is not intercepted by it, so this has to be checked by reading its diff.

If a task appears to need one of these to pass, stop. That is a signal the design is wrong,
not that the rule is negotiable.

## Worker lifecycle

Write a bounded prompt under `harness/codex/prompts/`, then start a foreground runner. The
orchestrator's shell tool is what backgrounds long jobs.

```bash
node scripts/codex-run.mjs run --id <worker-id> --prompt-file harness/codex/prompts/<prompt>.md
node scripts/codex-run.mjs status --id <worker-id>
node scripts/codex-run.mjs last  --id <worker-id> --chars 4000
node scripts/codex-run.mjs log   --id <worker-id> --lines 60
node scripts/codex-run.mjs resume --id <worker-id> --prompt-file harness/codex/prompts/<follow-up>.md
node scripts/codex-run.mjs list
```

1. `run` records the arguments and streams stdout and stderr into `.velmor/codex/`.
2. `status` reports `DONE`, `FAILED(<code>)` or `BLOCKED(<signal>)`.
3. `last` reads the final message, which is the concise handoff.
4. `log` reads recent output when the final message is missing or unclear.
5. `resume` continues the exact recorded session, by session id. It also replays the sandbox
   the worker was started with: `codex exec resume` has no `--sandbox` flag, so without that
   override a resumed read-only Verify worker would come back with write access. The ledger
   banner records the effective value as `sandbox: ...` if you need to check.
6. **Then verify it yourself**: read the diff and run the gate. Steps 1-5 are the worker's
   account of what it did.

A signal is only attached to a run that exited non-zero. `signal=` on a `DONE` worker is not a
thing that can happen; if you see one, the classifier is wrong, not the run.

Do not use the MCP `codex` tool for implementation or any long task. Its request can time
out and the work is lost mid-flight. Reserve it for short dialogue, one independent review,
and image generation; use the runner for anything that takes minutes.

## Fallback ladder

The ladder is **Codex worker -> Cursor `generator` subagent -> orchestrator**, and it is
descended only when the rung above is provably blocked. Because Codex is the default
implementer rather than an option, moving down a rung is a deviation that must be named in the
handoff: which rung, which signal, which worker id.

| Signal | Immediate response | Next owner |
|--------|--------------------|------------|
| `RATE_LIMITED` | Stop retrying Codex. Keep the prompt and the evidence. | Cursor `generator` subagent |
| `CONTEXT_LIMIT` | Reduce the task to a bounded file list, then resume once on the same session id | `generator` if still blocked |
| `AUTH_ERROR` | Do not paste credentials and do not create an API key. Record the blocker. | `generator` |
| The same issue fails twice | Stop repeating the same path. Record both failures. | `generator`, then the orchestrator |

The orchestrator may finish a bounded task directly only after an earlier owner is blocked or
has failed twice, and it reports "implemented by the orchestrator because <reason>". If
finishing it needs new authority, an external credential, or a changed product decision, stop
and ask the human.

`codex-gate.cjs` enforces the top of this ladder: a product-code write with no worker behind it
is refused, so skipping rung 1 is not a choice the agent can quietly make.

## Acceptance

- Read the actual diff. Not the summary, not the exit code.
- Run the gates the change requires, and quote the output:
  `uv run ruff check`, `uv run python -m pytest packages velmor -q`,
  `uv run python -m compileall -q packages velmor`.
- `/rights-verify` for anything touching rights, screening, connectors or the gate.
- `/ux-verify` for anything a buyer reads or acts on. The screenshots are the evidence.
- A Verify FAIL returns to the implementer once with the exact failing evidence. Not twice
  with the same evidence: that is the ladder, not a loop.
- If peers disagree, adjudicate against `AGENTS.md`, the OpenSpec specs, and command output.
  Prefer the claim that can be tested over the claim that reads better.
- Record a recurring failure pattern in `harness/lessons.md`.

## Session continuity

`.velmor/codex/` is the worker ledger. For worker `<id>` the runner writes `<id>.meta.json`,
`<id>.log`, `<id>.err`, `<id>.last.md` and `<id>.exit.json`. The CLI prints `session id:
<uuid>` on stderr, and `resume --id <id>` reads that exact id.

Never resume with "the last session": several workers share one working directory, so the
most recently finished session may belong to a different task. Prompts and worker state are
git-ignored; a ruling that matters goes into OpenSpec or a tracked harness document.

## Codex writes are not intercepted

`secret-guard.cjs` sees Cursor's tool calls. It never sees Codex's. Codex can write a secret
and nothing will deny it, so read its diff before staging. Never let a worker write
`packages/*/.env.*`, and never let it write anything under `~/.codex`.
