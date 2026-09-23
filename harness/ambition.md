# Harness ambition

**What "better" means here.** A harness is not measured by how many skills, rules and
servers it contains. It is measured by whether a task that used to close badly now closes
well. Volume that does not change an outcome is cost: more context loaded per turn, more
files to keep consistent, more places for a silent inconsistency to hide.

So the target for this repository is three specific properties, in order:

1. **Nothing important fails silently.** A predicate that matters is a sensor with a
   non-zero exit code, not a paragraph. `scripts/harness-status.mjs` and
   `scripts/selftest.mjs` are the shape of that.
2. **Independent verification is structural, not optional.** The agent that writes does
   not grade. Where a second model family is available, it is used, because a reviewer
   that thinks like the author misses what the author missed.
3. **The environment learns.** A defect that recurs produces a change to the environment,
   recorded in `harness/lessons.md`, not another one-off fix.

And one that was learned the hard way on 2026-09-23, so it is stated separately:

4. **A component that has never executed is unverified, and documentation is not evidence.**
   The Codex worker runner was written, documented and reviewed, and had never started a
   single worker. Three defects were hiding behind that - a documented prompt workflow that
   could not be executed, a resume that silently escalated a read-only worker to write
   access, and a classifier that reported a successful run as an authentication failure.
   None was visible in a diff, and none would have been caught by a review. A surface joins
   the harness when it has been run once on real input with its output recorded, not when
   its file exists.

## The gap this work closed

Recorded 2026-09-23, before this round of harness work. The `Before` column is what the
repository actually had; the `After` column is what it has now.

| Area | Before | After |
|------|--------|-------|
| Custom subagents | None. Only Cursor built-ins and the `bugbot`/`security-review` reviewers | 6 project subagents, mirrored for Cursor, Claude and Codex by `sync-agents.mjs` |
| Codex channel | MCP tool and a good skill document, but long work had to go through a transport with a timeout | Durable runner with a ledger, resume by exact session id, a review command, and a signed-off smoke test proving the channel starts and returns |
| Hooks | preToolUse, beforeShellExecution, postToolUse (5 scripts) | 9 scripts across 7 events, including sessionStart, beforeMCPExecution, afterFileEdit and stop |
| Sensors | `setup-mcp.mjs` only, and it did not follow the `run-mcp` indirection | `harness-status.mjs` (40+ checks) and `selftest.mjs` (66 injected-defect and contract tests) |
| Harness state | `.superpowers/sdd/` only | `.velmor/` for worker, edit and eval ledgers; git-ignored and checked for. Worker prompts are tracked in `harness/codex/prompts/` |
| Harness documents | None; everything lived in `AGENTS.md` and rule files | `harness/` with the loop, the surface map, the peer protocol and factory memory |
| Harness self-improvement | Informal | `/diagnose`, `/improve-harness`, `/eval`, `/harness-status`, and `lessons.md` |
| MCP reliability | Every `npx` server started concurrently with no lock | Serialized launcher with a cross-process lock and one alias table |
| Ignore file | None | `.cursorignore` (see the note below) |
| The spec contract | `config.yaml` could stop parsing with nothing failing but a warning | `harness-status.mjs` FAILs when OpenSpec is ignoring the config |

### Note: `.cursorignore`

`harness-status.mjs` requires `.cursorignore`. It is not true that an agent cannot create it:
the file write tool is denied, because `.cursorignore` changes the agent's own index, but the
shell creates it without complaint. The working procedure is therefore "write it through the
shell", not "ask a human" - an important distinction, because the first version of this note
said the latter and the file stayed missing across two sessions.

The wider consequence of the same rule is the reason Codex prompts are tracked in
`harness/codex/prompts/`: Cursor denies an agent both read and write on any path in
`.cursorignore`, so a workflow that stores what the agent must author under `.velmor/` is a
workflow nobody can execute.

## Adopted patterns, with sources

| Pattern | What it means here | Source |
|---------|--------------------|--------|
| Guides + sensors + loops | Rules and skills guide; scripts and hooks decide; the loop re-runs them | [Harness engineering](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html) |
| Planner-Generator-Evaluator | Planning, building and grading in separate contexts | [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) |
| Context layering (L1/L2/L3) | Load the always-on contract, then the stage's skills, then detail on demand | [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| Filesystem-ledger loop | Keep state on disk and survive a context reset | [Ralph loop](https://ghuntley.com/ralph/) |
| Full Cursor surface use | Rules, skills, commands, subagents, hooks, MCP, ignore file | [Cursor docs](https://cursor.com/docs/context/rules) |

## Non-goals

- Do not clone another project's skills because they look like richness. A skill that
  duplicates a paragraph of `AGENTS.md` is worse than no skill.
- Do not add an MCP server that cannot resolve or that duplicates a shell command.
- Do not measure the harness by folder count, and do not report a surface as present
  because a file exists - run the sensor.
- Do not add a rule that a hook could enforce instead.
