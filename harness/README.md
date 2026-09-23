# The Velmor harness

This directory is the operating manual for the **agent harness** - the rules, skills,
commands, hooks, subagents, MCP servers and scripts that surround the product code. It is
not part of the product. `AGENTS.md` is the contract every agent reads; these documents
are the detail that does not belong in that contract.

Read `ambition.md` first: it says what "better" means here and why the harness is not
measured by how many files it contains.

## The canonical loop

    1. Plan      OpenSpec: proposal, specs, design, tasks.        HUMAN CHECKPOINT
    2. Implement One fresh implementer subagent per task, then a task reviewer.
    3. Verify    Run the gates and keep the output. Evidence, not summary.
    4. Evaluate  /eval and /review - independent, never self-graded.
    5. Domain    /rights-verify  (does the gate still refuse what it must)
                 /ux-verify      (can a buyer actually see and buy)
    6. Repair    Back to the implementer. Bounded fix loop.
    7. Integrate Merge, PR or keep.                               HUMAN CHECKPOINT
    8. Improve   /improve-harness -> harness/lessons.md

`/ship <task>` runs this end to end and stops only at the two checkpoints.

## Commands

| Command | Purpose |
|---------|---------|
| `/ship <task>` | The whole loop, autonomously, with two human checkpoints |
| `/eval` | Independent Evaluator grading against a fixed rubric |
| `/review` | `bugbot` + `security-review` as the merge gate |
| `/rights-verify` | Proves the publication gate still refuses what it must |
| `/ux-verify` | Drives the running shop; screenshots are the evidence |
| `/diagnose` | Root cause of a harness, tooling or agent failure |
| `/improve-harness` | Repeated failure -> rule, hook, sensor or spec |
| `/harness-status` | Is the harness complete and consistent on this machine |
| `/opsx-*` | OpenSpec: explore, propose, apply, sync, update, archive |

## Subagents

Project subagents live in `.cursor/agents/` and are mirrored into `.claude/agents/` and
`.codex/agents/` so all three agent runtimes see them.

| Subagent | Role | Writes? |
|----------|------|---------|
| `planner` | Task -> OpenSpec artifacts | OpenSpec only |
| `generator` | One task, one context | Yes |
| `evaluator` | Grades against `/eval` | No |
| `rights-auditor` | Audits the rights contract | No |
| `surface-auditor` | Audits what a buyer sees | No |
| `python-debugger` | Root cause of a failing command | Yes, minimally |

## Health

```bash
node scripts/harness-status.mjs   # surfaces, mirrors, hooks, MCP, Codex, OpenSpec
node scripts/selftest.mjs         # do the harness scripts honour their own contracts
node scripts/setup-mcp.mjs        # what each MCP alias resolves to, and what needs a value
node scripts/sync-agents.mjs      # mirror .cursor/agents/ into the Claude and Codex runtimes
```

`harness-status.mjs` is the sensor. It fails on a harness that is incomplete or internally
inconsistent, which is the failure mode this directory exists to make visible. What it checks:

- the toolchain (node, uv, git, docker) and which of those is a machine-level gap, not a
  repository defect;
- every load-bearing surface: `AGENTS.md`, `.cursorignore`, the harness docs, the rule files,
  the scripts;
- subagent parity across `.cursor/agents/`, `.claude/agents/` and `.codex/agents/`;
- that every script named in `hooks.json` exists;
- that every `run-mcp` alias in `mcp.json` resolves in the alias table;
- that the Codex binary resolves, and how many workers the ledger holds;
- whether more than one agent session has written files recently, because a test run from a tree
  with two writers in it is not a measurement;
- that `.velmor/` is git-ignored, so harness state cannot be committed;
- that `openspec validate --strict --all` passes **and** that OpenSpec is not silently
  ignoring `config.yaml` - a config it cannot parse is warned about, ignored, and still
  reported as valid, so the exit code is not enough.

A `FAIL` means the harness is wrong and the exit code is 1. A `WARN` means this machine
cannot exercise a part of it - no Docker, no Codex CLI, no `openspec` on `PATH` - and the exit
code stays 0. An `INFO` line is inventory.

None of it is trusted until it has been shown to fail: `scripts/selftest.mjs` drives the
sensors against injected defects (a missing surface, an unmirrored subagent, an unresolvable
alias, an unreadable `config.yaml`) and asserts the specific `FAIL` line each produces.

## Codex, the second agent family

Codex runs a different model family, so its blind spots are uncorrelated with ours. It is
used two ways, and the choice between them matters:

| Transport | Use for | Why |
|-----------|---------|-----|
| `codex` MCP tool | Short dialogue, one independent review, image generation | An MCP request has a timeout |
| `scripts/codex-run.mjs` | Implementation and verification that runs for minutes | Durable ledger, resumable, survives the timeout |

Full protocol: `dual-agent.md`. Operator detail: `codex-workers.md`. A worker's own report
is never evidence.

### Codex is not optional here: it is the default implementer

Product code under `packages/`, `velmor/` and `storefront/` is written by a Codex worker, and
Cursor verifies the diff. Cursor implements only after a classified failure
(`RATE_LIMITED` / `CONTEXT_LIMIT` / `AUTH_ERROR`) or two failed attempts, and it says so.

That ordering used to be prose, and prose had no teeth: `/ship` dispatched a Cursor
implementer, Codex was one optional row in a table, and an agent that simply did the work
itself produced no failure anywhere. `.cursor/hooks/codex-gate.cjs` is the fix. It denies a
write to product code unless the worker ledger holds a worker for this session, so the
requirement is enforced rather than requested.

Never gated, because delegating them would be wrong rather than merely unnecessary: the
verdict path (`packages/services/src/rights/**`, `screening/**`), and the harness itself
(`.cursor/**`, `harness/**`, `scripts/**`, `AGENTS.md`). `VELMOR_CODEX_GATE=off` opens the
gate for one session for a documented exception.

The gate cannot see Codex's own writes - hooks intercept Cursor tool calls only - so after a
worker you read the diff and run the gate the hook would have run. For `storefront/**` that is
the locale parity check, and `/ux-verify` before completion.

Start a worker from `harness/codex/prompts/build-task.md`.

After any change to the launcher, the runner or the Codex CLI, prove the channel still works
with the read-only prompt in `harness/codex/prompts/smoke-test.md`. `harness-status.mjs` only
proves the binary resolves; a ledger that starts and returns a final message is the evidence
that the channel is intact. Pick a fresh `--id` each time: the runner refuses to reuse one,
because reusing an id would overwrite the record of the run you are comparing against.

## Where state lives

| Path | Contents | Tracked? |
|------|----------|----------|
| `.velmor/codex/` | Codex worker meta, logs, last message, exit record | No |
| `.velmor/edit-ledger/` | One line per agent file edit | No |
| `.velmor/eval/`, `.velmor/diagnose/` | Evaluator and diagnosis notes | No |
| `.superpowers/sdd/` | Subagent-driven-development ledger and per-task briefs | No |
| `harness/codex/prompts/` | Codex worker prompts | Yes |
| `harness/lessons.md` | Factory memory. Append-only, and tracked | Yes |
| `openspec/` | The product contract | Yes |

Worker prompts are tracked and the worker ledger is not, and the split is not cosmetic:
`.velmor/` is listed in `.cursorignore`, so Cursor denies an agent read and write on it.
A prompt stored under a path the orchestrating agent cannot write is a workflow nobody can
execute. Prompts are also the task statement a reviewer needs to judge a worker's diff, so
they belong in the diff.

Durable rulings belong in `openspec/` or in a tracked harness document. Everything under
`.velmor/` is orchestration state and is git-ignored.

## Rules for changing the harness

- The harness is governed by `.cursor/hooks/policy-guard.cjs`: edits to `.cursor/rules/`,
  `.cursor/hooks*`, `.cursor/commands/`, `.cursor/mcp.json`, `AGENTS.md` and
  `openspec/config.yaml` require human approval. That is the point, not an obstacle.
- `AGENTS.md` is the only channel that reaches an external agent such as Codex for free.
  A convention that must bind Codex belongs there, not only in a `.mdc` file.
- Add a constraint in the strongest place the failure allows: `AGENTS.md` -> hook ->
  sensor -> skill -> rule. See `/improve-harness`.
- Never fork this harness into `storefront/` or into a package.
