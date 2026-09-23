# Cursor surface map

Everything Cursor's agent reads from this repository, with what it is for and where the
documented behaviour comes from. Skills, hooks, commands and MCP are only part of it; the
surfaces below are the whole set this harness uses.

| Surface | Path | Role | Source |
|---------|------|------|--------|
| `AGENTS.md` + `CLAUDE.md` | `/AGENTS.md`, `/CLAUDE.md` | The always-on contract, for Cursor **and** external agents such as Codex | Project convention |
| Rules | `.cursor/rules/*.mdc` | `alwaysApply` conventions, or path-scoped detail | [Rules](https://cursor.com/docs/context/rules) |
| Skills | `.cursor/skills/*/SKILL.md`, `.agents/skills/*/SKILL.md` | Procedures loaded on demand | [Skills](https://cursor.com/docs/context/skills) |
| Commands | `.cursor/commands/*.md` | Slash entry points a human starts | [Commands](https://cursor.com/docs/agent/commands) |
| Subagents | `.cursor/agents/*.md`, `.claude/agents/`, `.codex/agents/` | Separate context windows for factory roles | [Subagents](https://cursor.com/docs/agent/subagents) |
| Hooks | `.cursor/hooks.json` + `.cursor/hooks/*.cjs` | Deterministic lifecycle gates | [Hooks](https://cursor.com/docs/agent/hooks) |
| MCP | `.cursor/mcp.json` | External tools | [MCP](https://cursor.com/docs/context/mcp) |
| Ignore | `.cursorignore` | Keeps build output and secrets out of the agent index | [Ignore files](https://cursor.com/docs/context/ignore-files) |
| Cloud agents | cursor.com team config | Separate from local `mcp.json`; not used here | [Cloud agents](https://cursor.com/docs/cloud-agents) |

Two consequences worth stating plainly:

- **`.cursorignore` is not a security boundary, and it is stronger than it looks.** It keeps
  paths out of the index and out of `@`-file suggestions, and Cursor also denies an agent's
  own `Read` and `Write` on a listed path. The terminal, the hooks and MCP tools can still
  reach everything in it, so `secret-guard.cjs`, `policy-guard.cjs` and
  `destructive-guard.cjs` remain the boundary. The practical consequence is the reason Codex
  prompts live in `harness/codex/prompts/` and not beside the worker ledger: a prompt under
  `.velmor/` cannot be written by the agent that has to write it.
- **A rule in `.mdc` does not reach Codex.** Codex reads `AGENTS.md` and nothing else from
  this repository. A convention that must bind it belongs in `AGENTS.md`.

## Subagents

Cursor reads `.cursor/agents/` and also `.claude/agents/` (Claude compatibility) and
`.codex/agents/` (Codex compatibility), and `.cursor/` wins on a name collision. The project
subagents are mirrored into all three so no runtime is second-class. Only `name`,
`description` and the prompt body are required; `readonly: true` restricts a subagent's
writes, which every auditing role here uses.

`.cursor/agents/` is the source and the other two are copies of it, never edited directly.
Edit one file, then run `node scripts/sync-agents.mjs`; it also removes a stale file from a
mirror, because a retired subagent left there is still loadable by that runtime.
`harness-status.mjs` fails on drift, and `scripts/selftest.mjs` runs
`sync-agents.mjs --check`, so an unmirrored subagent cannot reach a commit unnoticed.

`description` is what the parent reads when deciding whether to delegate. It must say *when*
to use the subagent, not what the subagent is. "Audits the rights contract. Use whenever
anything under `packages/services/src/rights/` changed." delegates; "Rights expert" does not.

## Hooks in use

| Event | Script | Why |
|-------|--------|-----|
| `sessionStart` | `session-start.cjs` | Inject the harness entry points and current state (open changes, last lesson); stamp `.velmor/session/epoch` so `codex-gate.cjs` can date the session |
| `preToolUse` | `secret-guard.cjs` | Deny a write containing a hardcoded credential |
| `preToolUse` | `codex-gate.cjs` | Deny a write to product code with no Codex worker behind it - the Codex-first requirement |
| `preToolUse` | `ui-guard.cjs` | Deny a storefront edit that hardcodes buyer-visible copy or a language |
| `preToolUse` | `policy-guard.cjs` | Require human approval for a rights-policy or harness file |
| `beforeShellExecution` | `destructive-guard.cjs` | Deny irreversible git, Docker and delete commands |
| `beforeMCPExecution` | `mcp-audit.cjs` | Deny the unsafe Codex sandbox/approval combination and destructive tool names |
| `postToolUse` | `lint-feedback.cjs`, `ui-feedback.cjs` | Return `ruff` violations and locale-key drift as context at edit time |
| `afterFileEdit` | `after-file-edit.cjs` | Append to the edit ledger |
| `stop` | `stop-gate.cjs` | One evidence follow-up when a session claims completion without proof |

Events deliberately not wired: `sessionEnd`, `subagentStop`, `preCompact`,
`afterAgentResponse`, the Tab hooks and `workspaceOpen`. Each would add a process spawn per
event without changing an outcome here.

`failClosed` is set per script to match its failure mode. The permission hooks are
fail-closed: a crashed write guard must not silently become a permissive one.
`destructive-guard` is not, on purpose - if Node itself is broken, blocking every shell
command would leave no way to diagnose it. `codex-gate` is not either, for the same reason: it
is a workflow gate, and a crashed workflow gate must not leave product code unwritable. It is
nonetheless written to reach an explicit decision on every path, and every path that can read
the worker ledger denies when no worker is recorded.

**What no hook can cover: Codex's own writes.** Hooks intercept Cursor tool calls, so a worker
editing `storefront/` bypasses `ui-guard` entirely. That is the reason `/ship` step 1 makes the
orchestrator read the diff and run the locale parity check by hand after every worker.

**Hook input is read through one module.** `.cursor/hooks/lib/hook-io.cjs` is the only place that
reads stdin, for two measured reasons:

- Cursor prefixes the payload with a **UTF-8 BOM** and `JSON.parse` rejects a leading U+FEFF.
  Every hook used to parse stdin directly, fail on the BOM, fall back to `{}` and do nothing -
  silently, on every event. A hardcoded live Stripe key was measured passing `secret-guard.cjs`
  because of it. `readPayload()` strips the BOM and reports a parse failure on stderr rather than
  swallowing it.
- The payload's `workspace_roots[0]` is the URL-ish `"/d:/Python/Velmor"`, and
  `path.join('/d:/Python/Velmor', '.velmor')` resolves to `D:\d:\Python\Velmor\.velmor` - a real
  directory on the drive root, not the workspace. `workspaceRoot()` normalises it.

`scripts/selftest.mjs` sends the BOM with every hook payload, so a regression fails the suite. If
a hook is added, it reads its input through `hook-io`; parsing stdin directly reintroduces a class
of failure that already happened once and is invisible in a diff.

## Commands in use

A command is a slash entry point a human starts, and the reason to have one is that the
procedure is long enough that an improvised version drifts.

| Command | Kind | What it runs |
|---------|------|--------------|
| `/ship` | orchestrator | The whole loop, with two human checkpoints |
| `/eval` | independent grader | Grades against a fixed rubric from a fresh context |
| `/review` | merge gate | `bugbot` + `security-review` |
| `/rights-verify` | domain runtime | Proves the gate still refuses what it must |
| `/ux-verify` | buyer-surface runtime | Drives the shop; screenshots are the evidence |
| `/harness-status` | sensor | Runs the harness sensors and reads them |
| `/diagnose` | diagnosis | Root cause before any fix |
| `/improve-harness` | improvement | Turns a repeated failure into a permanent constraint |
| `/opsx-*` | contract | OpenSpec explore, propose, apply, sync, update, archive |

`/eval` is the one that is easy to skip and expensive to skip: it is the only grader that is
neither the author nor the author's test suite. A change graded in the session that produced
it was not independently evaluated, and saying so is required.

## Project skills in use

`.cursor/skills/` holds the procedures this project authored; `.agents/skills/` holds the
installed collections. Both are loaded on demand, never always-on.

| Skill | Loaded when |
|-------|-------------|
| `run-the-project` | running, testing or troubleshooting the product |
| `rights-engine` | anything on the verdict path |
| `source-connector` | adding or changing a discovery source |
| `agent-graph` | changing the auditor graph |
| `storefront-ux` | anything a buyer reads or acts on |
| `codex-second-agent` | dispatching Codex |
| `harness-peers` | running Cursor and Codex as peers |
| `pge-harness` | structuring a non-trivial `/ship` so generation and grading stay separate |
| `ralph-loop` | a task that keeps stalling in the same context |
| `harness-improve` | turning a failure into a permanent constraint |
| `context-layers` | deciding how much to load, or recovering after a full context |

## Environment and session

`session-start.cjs` sets two variables for the session:

| Variable | Meaning |
|----------|---------|
| `VELMOR_ROOT` | The workspace root, for scripts and hooks that should not guess |
| `VELMOR_HARNESS` | `1` when running inside the harness session |

Two hooks can be switched off for a session: `VELMOR_EDIT_LEDGER=0` and
`VELMOR_STOP_FOLLOWUP=0`.
