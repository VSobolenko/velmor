---
name: "/ship"
id: "ship"
category: "Workflow"
description: "Autonomous orchestrator: propose -> implement -> verify -> rights-verify -> review -> finish -> archive"
---

# /ship — autonomous agent harness

Single entry point for end-to-end autonomous work. The user hands over a task
once; this command plans it, has a **Codex worker** implement each task (with a task
review and a bounded fix loop), verifies it with real evidence, dispatches the
checker agents, and returns "done + evidence" — stopping for the human only at two
checkpoints.

Cursor is the orchestrator and the verifier. It does not write product code while a
Codex worker could: a second model family is what makes the verification
independent, and an agent that writes and then grades has one set of blind spots.

This command is glue over already-installed tooling. Do not reimplement the roles
below; invoke them.

## Roles (all already installed)

| Role | Implementation |
|------|----------------|
| Orchestrator (controller) | this command — you, the current agent |
| Contract | OpenSpec specs (`openspec/specs/**`) + `/opsx-propose`, `/opsx-apply`, `/opsx-archive` |
| Writer / implementer (default) | **Codex worker** — `scripts/codex-run.mjs run`, prompt from `harness/codex/prompts/build-task.md`. See `harness/dual-agent.md` |
| Writer / implementer (fallback) | fresh `generalPurpose` subagent per task — `.agents/skills/subagent-driven-development/implementer-prompt.md`. Only after a classified Codex failure or two failed attempts |
| Writer / implementer (last resort) | the orchestrator itself, and only with that stated in the output |
| Task checker | task reviewer subagent — `.agents/skills/subagent-driven-development/task-reviewer-prompt.md` |
| Final checker (bugs) | `bugbot` subagent (see `/review`) |
| Final checker (security) | `security-review` subagent (see `/review`) |
| Domain runtime checker | `/rights-verify` — does the publication gate still refuse what it must |
| Buyer-surface runtime checker | `/ux-verify` — can a buyer actually see, understand and buy, in every locale |
| Independent Evaluator | `/eval` — grades against a fixed rubric from a fresh context, never patches |
| Codex-first enforcer | hook `codex-gate.cjs` — refuses a product-code write with no worker behind it |
| Harness sensor | `node scripts/harness-status.mjs` and `node scripts/selftest.mjs` |
| Policy enforcer | hooks `secret-guard.cjs`, `policy-guard.cjs`, `ui-guard.cjs`, `destructive-guard.cjs`, `mcp-audit.cjs` (automatic) |
| Evidence gate | `.agents/skills/verification-before-completion/SKILL.md` |
| Integration gate | `.agents/skills/finishing-a-development-branch/SKILL.md` |

## The two human checkpoints

Only these stop the loop. Everything else runs autonomously.

1. **Plan approval** — after proposing, present proposal + specs + tasks and STOP
   until the human says go.
2. **Integration** — after review is green, present merge/PR/keep options and STOP
   for the human's choice.

Committing, merging, pushing and archiving are integration decisions: do not
perform them silently. Per-task WIP commits by implementers are fine as recovery
points; squash them before checkpoint 2.

There is a third stop that is not a checkpoint but a hard requirement: if the task
turns out to need a change to `license_grants.py`, `publication_gate.py`,
`proposal.md` scope, or any other surface that changes what Velmor may legally
publish, stop and ask. `policy-guard.cjs` will ask for you on the code side; do
not treat that approval as approval of a scope change.

## Steps

### 0. Classify and plan (OpenSpec)

- If no OpenSpec change exists for this task, run `/opsx-propose <task>`. Read
  `AGENTS.md`, `.cursor/rules/*.mdc` and existing `openspec/specs/**` first so the
  plan honours the conventions and the fixed domain vocabulary.
- If a change already exists, reuse it (`openspec status --change "<name>" --json`).
- Present the plan. **CHECKPOINT 1** — stop until "go". Do not begin implementation
  in the same turn.

### 1. Implement (Codex first)

**Codex writes the code. You verify it.** The default owner of every implementation task is a
Codex worker; `.cursor/hooks/codex-gate.cjs` refuses a product-code write that has no worker
behind it, so this is not optional and not a preference.

For each task in `tasks.md`:

1. Isolate the work first (`.agents/skills/using-git-worktrees/SKILL.md`). Never implement on
   main/master without consent.
2. Keep the ledger at `.superpowers/sdd/<plan>/progress.md`. It is the recovery map after
   context loss; trust it over recollection.
3. Copy `harness/codex/prompts/build-task.md` to `harness/codex/prompts/<task-id>.md`, fill in
   the outcome, the exact file list, the inputs and the verification boundary, then start the
   worker:

   ```bash
   node scripts/codex-run.mjs run --id <task-id> --prompt-file harness/codex/prompts/<task-id>.md \
     --sandbox workspace-write --effort high --label '<task>'
   ```

   One worker per task. Independent tasks with disjoint file lists may run in parallel; two
   writers on the same file is a defect, not concurrency.
4. `node scripts/codex-run.mjs status`, then `last`, and **read the diff**. A worker's `DONE`
   is a claim.
5. Dispatch ONE task reviewer subagent over the diff, and run the fix loop (at most 5 rounds)
   on spec or quality failures. Resume the same worker with `resume --id <task-id>` for a
   narrow follow-up; do not start a fresh worker on the same task to dodge a failure.
6. Ledger every completion and every ruling. Do not pause between tasks to check in.

Falling back to rung 2 means writing down why, with the signal:

| Codex outcome | Next owner |
|---------------|-----------|
| `RATE_LIMITED` | Cursor implementer subagent, and say so in the output |
| `CONTEXT_LIMIT` | reduce the task to a bounded file list and `resume` once; if still blocked, Cursor implementer |
| `AUTH_ERROR` | do not paste a credential; report it, then Cursor implementer |
| same failure twice | stop repeating it; Cursor implementer, then the orchestrator |

Never send these to Codex at all: `packages/services/src/rights/**`,
`packages/services/src/screening/**` (the verdict path — `policy-guard.cjs` wants a human),
and the harness itself (`.cursor/**`, `harness/**`, `scripts/**`, `AGENTS.md`).

**The hook cannot see Codex's writes.** Hooks intercept Cursor tool calls only, so the guards
that normally run on a write — `secret-guard`, `ui-guard`, the locale parity check — do not run
on a worker's edit. After every worker you must therefore read the diff and run the gate the
hook would have run: for `storefront/**` that is `npm --prefix storefront run lint` (locale
parity) and, before completion, `/ux-verify`.

Apply the stack skills before the work they cover — as instructions to the worker's prompt,
since Codex does not read `.cursor/rules/` or `.cursor/skills/`:
- LangGraph state, nodes, persistence, interrupts → `langgraph-*` skills from
  `langchain-ai/langchain-skills`
- One structured extraction → `building-pydantic-ai-agents`
- Tracing and instrumentation → `logfire-instrumentation`
- Prompt versions, cost and evals → `langfuse`
- Any change under `packages/services/src/rights/` → reread
  `.cursor/rules/06-rights-engine.mdc`

### 2. Verify (evidence)

Before any "done" claim, run the `.agents/skills/verification-before-completion/SKILL.md`
gates and capture the real output (pass/fail plus the key line):

- Python changed → `uv run ruff check` and `uv run python -m pytest packages -q`
- Runtime sanity → `uv run python -m compileall -q packages velmor`
- Dependency or version changed → `uv sync` must succeed
- Spec or planning changed → `openspec validate --strict "<change>"`
- Harness changed (rules, hooks, commands, agents, MCP) → `node scripts/harness-status.mjs`
  and `node scripts/selftest.mjs`; add `node scripts/setup-mcp.mjs` for an MCP change
- Storefront changed → `npm --prefix storefront run lint` (it checks dictionary
  parity) and `npm --prefix storefront run build`

Never report a check as passing without its output.

### 3. Domain runtime verify

Run `/rights-verify`. Static review cannot see whether the gate still refuses what
it must, and a gate that has quietly stopped refusing passes every lint and unit
test that was written before the change. This step drives the blast radius of the
change and reports PASS or FAIL. Failures enter the same fix loop as review
blockers: resume the worker (`resume --id <task-id>`), or resume the fallback implementer if
that is who wrote it; then scope a re-review and re-run `/rights-verify` on
the affected surface.

### 3b. Buyer-surface runtime verify

This step exists because a complete commerce layer once shipped whose entire buyer
surface was a list of source filenames in one hardcoded language, and every gate
above it passed.

Run `/ux-verify` whenever the change touches anything a buyer reads or acts on:
`storefront/**`, a buyer-facing route under `packages/api/**`, or a preview or
delivery response. It drives the running shop with a browser, looks at the result
at desktop and mobile width in every locale, and reports with screenshots as
evidence. A diff cannot show that a page has no images; this step can.

Failures enter the same fix loop as review blockers. Do not mark a buyer-facing
task complete on the strength of a green suite and a rendered HTML string in a
test — that is exactly the class of evidence that missed this before.

### 3c. Grade (independent Evaluator)

Run `/eval`. The evaluator grades the change against the fixed rubric from a fresh
context, and the separation is the point: a reviewer holding the author's context
shares the author's blind spots, and a suite written by the author cannot see what the
author did not think to check. For a second model family, a read-only Codex worker
(`node scripts/codex-run.mjs review --id <id> --uncommitted`) is the strongest available
third opinion — its verdict is input, never proof.

A score below 4 on any criterion is a blocking finding and enters the same fix loop.
Never grade work produced in the same session without saying so explicitly.

### 4. Review (checkers)

Dispatch `/review`, which launches `bugbot` and `security-review` in parallel. If
it reports CHANGES REQUIRED with blockers, run the fix loop: hand the findings back
to whoever wrote it — the worker first, the fallback implementer if the ladder moved — then a
scoped re-review. Bounded at 5 rounds; adjudicate any
residual per `subagent-driven-development` and ledger every ruling.

### 5. Finish (integration)

Re-run the verification suite from step 2, then run
`.agents/skills/finishing-a-development-branch/SKILL.md` and **CHECKPOINT 2** —
present exactly the merge/PR/keep options and wait. Execute the choice; do not
merge or push without it.

### 6. Archive

After integration completes, run `/opsx-archive` to sync the change's delta specs
into `openspec/specs/` and close the change. If `ENGINE_VERSION` moved during the
work, say so in the archive summary.

## Output

```
## /ship complete — <task>

**Change:** <change-name>
**Plan:** <proposal path>
**Implementation:** N tasks, 1 ship commit <sha>

### Who implemented
- worker: <worker ids and the tasks each owned>
- fallbacks: <none | the rung, the signal, and why>

### Verification (evidence)
- ruff: <pass/fail + line>
- pytest: <pass/fail + line>
- compileall: <pass/fail + line>
- openspec validate: <pass/fail + line>
- storefront lint/build: <pass/fail + line or n/a>

### Domain verification
- rights-verify: <suites passed / failed>

### Buyer-surface verification
- ux-verify: <pages x widths x locales driven / failures> (shots: <paths>)

### Evaluation
- eval: <per-criterion scores, verdict PASS/FIX/KILL>
- harness-status / selftest: <pass/fail + line, or n/a>

### Review
- bugbot: <findings count>
- security-review: <findings count>

### Effect on what Velmor may publish
<new goods publishable / nothing changed / refusals added or removed>

### Rulings I made
- <each ruling + what it costs if wrong>

### Integration
<merge/PR/keep — pending your decision at Checkpoint 2>
```

## Guardrails

- Only the two checkpoints stop the loop. Do not stall for anything else.
- **Codex implements; you verify.** Do not implement a task in the controller session while a
  worker could have done it. `codex-gate.cjs` will refuse the write; that refusal is the rule
  working, not an obstacle. Fall back only on a classified failure or two failed attempts, and
  state which.
- Never merge, push or archive without checkpoint 2.
- Never let an implementer spawn its own reviewer. Review comes from you.
- Never fix findings yourself in the controller session; resume the worker, or the fallback
  implementer.
- Never treat a worker's `DONE` as evidence. Read the diff, run the gate, quote the output.
- Never implement a task inline in the controller without saying so in the output.
- Evidence before "done", always. No "should pass", no trusting an agent's own
  success report.
- Never relax a rights rule to make a task pass. If a task needs the rule bent, the
  task is wrong.
- Never let a model produce a `RightsVerdict`. Models propose evidence.
- Never commit secrets. `secret-guard.cjs` is the backstop, not a licence to relax.
- Never mark a buyer-facing surface done from tests alone. `/ux-verify` produces
  screenshots; without them the surface is unverified, and the word for that is
  "unverified", not "done".
- Never introduce a buyer-facing string outside the locale dictionaries, and never
  choose a language for the buyer. `ui-guard.cjs` will deny the edit; that denial is
  the rule working, not an obstacle to work around.
