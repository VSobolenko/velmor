---
name: "/ship"
id: "ship"
category: "Workflow"
description: "Autonomous orchestrator: propose -> implement -> verify -> rights-verify -> review -> finish -> archive"
---

# /ship — autonomous agent harness

Single entry point for end-to-end autonomous work. The user hands over a task
once; this command plans it, implements it (fresh implementer subagent per task
plus a task review and a bounded fix loop), verifies it with real evidence,
dispatches the checker agents, and returns "done + evidence" — stopping for the
human only at two checkpoints.

This command is glue over already-installed tooling. Do not reimplement the roles
below; invoke them.

## Roles (all already installed)

| Role | Implementation |
|------|----------------|
| Orchestrator (controller) | this command — you, the current agent |
| Contract | OpenSpec specs (`openspec/specs/**`) + `/opsx-propose`, `/opsx-apply`, `/opsx-archive` |
| Writer / implementer | fresh `generalPurpose` subagent per task — `.agents/skills/subagent-driven-development/implementer-prompt.md` |
| Task checker | task reviewer subagent — `.agents/skills/subagent-driven-development/task-reviewer-prompt.md` |
| Final checker (bugs) | `bugbot` subagent (see `/review`) |
| Final checker (security) | `security-review` subagent (see `/review`) |
| Domain runtime checker | `/rights-verify` — does the publication gate still refuse what it must |
| Buyer-surface runtime checker | `/ux-verify` — can a buyer actually see, understand and buy, in every locale |
| Policy enforcer | hooks `secret-guard.cjs`, `policy-guard.cjs`, `ui-guard.cjs`, `destructive-guard.cjs` (automatic) |
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

### 1. Implement (subagent-driven)

Follow `.agents/skills/subagent-driven-development/SKILL.md` over the OpenSpec
`tasks.md`:

- Isolate the work first (`.agents/skills/using-git-worktrees/SKILL.md`). Never
  implement on main/master without consent.
- Keep the ledger at `.superpowers/sdd/<plan>/progress.md`. It is the recovery map
  after context loss; trust it over recollection.
- For each task: extract the brief from `tasks.md` and its spec, dispatch ONE fresh
  implementer subagent (never parallel implementers, never inline implementation in
  the controller session), then ONE task reviewer. Run the fix loop (at most 5
  rounds) on spec or quality failures. Ledger every completion and every ruling.
- Do not pause between tasks to check in. Continuous execution.

Apply the stack skills before the work they cover:
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
- Harness changed (rules, hooks, commands, MCP) → `node scripts/setup-mcp.mjs`
- Storefront changed → `npm --prefix storefront run lint` (it checks dictionary
  parity) and `npm --prefix storefront run build`

Never report a check as passing without its output.

### 3. Domain runtime verify

Run `/rights-verify`. Static review cannot see whether the gate still refuses what
it must, and a gate that has quietly stopped refusing passes every lint and unit
test that was written before the change. This step drives the blast radius of the
change and reports PASS or FAIL. Failures enter the same fix loop as review
blockers: resume the implementer, scope a re-review, re-run `/rights-verify` on
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

### 4. Review (checkers)

Dispatch `/review`, which launches `bugbot` and `security-review` in parallel. If
it reports CHANGES REQUIRED with blockers, run the fix loop: hand the findings back
to the implementer, then a scoped re-review. Bounded at 5 rounds; adjudicate any
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
- Never merge, push or archive without checkpoint 2.
- Never let an implementer spawn its own reviewer. Review comes from you.
- Never fix findings yourself in the controller session; resume the implementer.
- Never implement a task inline in the controller. Always dispatch via the Task tool.
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
