# Codex worker operator guide

Use a Codex worker for bounded, durable engineering work: an implementation in a worktree,
a long investigation, or an independent verification. The runner keeps every artefact in
`.velmor/codex/`. It does not make a worker's self-report authoritative.

Read `dual-agent.md` first for the role cards and the fallback ladder.

## A worker is required, not optional

Implementation under `packages/`, `velmor/` and `storefront/` is a Codex worker's job, and
`.cursor/hooks/codex-gate.cjs` enforces it: a product-code write with no worker recorded for
the current session is denied. The check reads this ledger, so the evidence is a recorded
session, never an assertion that one ran.

Start implementation prompts from `harness/codex/prompts/build-task.md` - an outcome, an exact
file list, the inputs, a verification boundary and a token budget. Codex does not read
`.cursor/rules/`, so a constraint you leave out of the prompt does not exist for the worker;
`AGENTS.md` is the one file it reads for free.

The gate stands aside for `packages/services/src/rights/**` and `screening/**` (a human
approves those) and for the harness itself. `VELMOR_CODEX_GATE=off` opens it for one session
when an exception is genuine; do not use it to avoid delegating.

Because hooks intercept Cursor tool calls only, a worker's edit is not seen by `secret-guard`
or `ui-guard`. Read the worker's diff and run the gate the hook would have run - for
`storefront/**`, the locale parity check.

## Commands

```bash
# Start one worker. The runner stays in the foreground; background it with your shell tool.
node scripts/codex-run.mjs run --id <id> --prompt-file harness/codex/prompts/<prompt>.md

# Independent review of the working tree, no prompt file needed.
node scripts/codex-run.mjs review --id <id> --uncommitted
node scripts/codex-run.mjs review --id <id> --base origin/main

# Inspect all workers, or one.
node scripts/codex-run.mjs list
node scripts/codex-run.mjs status --id <id>

# Read the final answer or recent output.
node scripts/codex-run.mjs last --id <id> --chars 4000
node scripts/codex-run.mjs log  --id <id> --lines 60

# Continue the exact recorded session with a follow-up prompt.
node scripts/codex-run.mjs resume --id <id> --prompt-file harness/codex/prompts/<follow-up>.md
```

`run` requires `--id` and `--prompt-file`. `review` requires `--id` and either `--base` or
`--uncommitted`. `resume` requires the same worker id and a new prompt file.

## `run` and `review` options

| Option | Values | Default | Use |
|--------|--------|---------|-----|
| `--cwd <dir>` | An existing directory | Repository root | Isolate the worker, typically a worktree |
| `--model <name>` | A model the installed CLI offers | Codex's configured model | Pick a cheaper model for mechanical work |
| `--effort <level>` | `none`, `low`, `medium`, `high`, `xhigh`, `max` | `medium` | Match reasoning cost to task risk |
| `--sandbox <mode>` | `read-only`, `workspace-write` | `workspace-write` | `read-only` for Verify |
| `--timeout-min <n>` | A positive number | No runner timeout | Kill a worker that exceeds a deliberate limit |
| `--label <text>` | Free text | Empty | Explain the worker in `status` output |
| `--instructions <file>` | A file path | Codex's default review prompt | `review` only: custom review instructions |

`danger-full-access` is **refused** by the runner, not accepted with a warning. A durable,
unattended worker is where unrestricted filesystem and process authority is most dangerous,
and `workspace-write` covers every Build and Verify task. If full access is genuinely
required, drive the task through the `codex` MCP tool, where `mcp-audit.cjs` still denies the
combination that removes the human from the loop.

## Prompt contract

A worker starts with an empty context. It has `AGENTS.md` and nothing else from this
repository, so a prompt that assumes shared context produces a confident wrong answer. Write
the prompt so it stands alone, in this order:

1. **Outcome.** One observable result.
2. **Scope.** The exact working directory and the exact files it may read and write.
3. **Inputs.** The specs, facts and files it must read first.
4. **Hard rules.** Forbidden files and actions, no secrets, no git mutations, and a
   restatement of anything from `.cursor/rules/` that must bind it, because Codex does not
   read `.mdc` files.
5. **Verification boundary.** The exact commands it may run:
   `uv run ruff check`, `uv run python -m pytest packages velmor -q`,
   `uv run python -m compileall -q packages velmor`. Nothing else.
6. **Network.** Codex's own model calls work, but every *command it runs* is
   network-isolated. Forbid anything that reaches out: no `uv sync`, no `docker`, no
   `pip install`, no database access. Say "run exactly one command, do not retry, stop
   immediately on failure" when a command might touch the network, because a retry loop can
   hang for many minutes.
7. **Token contract.** State the budget, require it to reserve enough for verification and
   handoff, and require `CONTEXT_LIMIT` rather than a guess or a silently dropped scope.
8. **Reply contract.** A fixed, machine-scannable last line.

Example ending:

```text
Do not run git. Do not edit outside the files listed above.
Run only the two commands in the verification boundary. Do not retry a failure.
Stay within the supplied budget; if the work cannot be completed without dropping scope,
reply exactly CONTEXT_LIMIT.
On success reply with exactly: DONE <comma-separated files>.
On failure reply with exactly: BLOCKED <one-line reason>.
```

Never put a secret in a prompt: prompts, metadata, stdout and stderr are durable local files.

## Reading output

1. `status --id <id>`.
2. On `DONE`, read `last`. Then read the diff and run the gate yourself.
3. On `FAILED`, `BLOCKED(...)`, or no final message, read `log` and the tail of the `.err`
   file.
4. Treat every claimed test result as unverified until you reproduce it.
5. Use `resume` only when a narrow follow-up can fix the same task safely. The runner replays
   the recorded sandbox, so a resumed Verify worker stays read-only.

After changing the launcher, the runner or the Codex CLI, prove the channel still works with
the read-only prompt in `harness/codex/prompts/smoke-test.md`. A worker ledger that starts and
returns a final message is the only evidence that the channel is intact; `harness-status.mjs`
only proves the binary resolves.

## Classified failures

A signal is only ever attached to a run that exited non-zero, because a successful run has no
failure to classify. The patterns are deliberately narrow: a false positive sends the
orchestrator to a different writer for a failure that never happened, which costs more than
the miss it was meant to catch. They live in `scripts/lib/codex-signals.mjs`, and
`scripts/selftest.mjs` asserts both the matches and the near-misses.

| Failure | Meaning | Reaction |
|---------|---------|----------|
| `RATE_LIMITED` | Usage, rate or quota limit | Do not retry. Hand the preserved task to the Cursor `generator` subagent |
| `CONTEXT_LIMIT` | Context or token limit | Reduce scope and resume once on the same session id; then `generator` |
| `AUTH_ERROR` | CLI login or session problem | Do not create or paste credentials. Use `generator` and report the auth issue |

An unclassified failure gets one evidence-driven resume. If the same issue happens twice,
stop retrying and use the ladder in `dual-agent.md`.

## Three workers in parallel

Create three prompts with disjoint write sets first:

```text
harness/codex/prompts/build-services.md
harness/codex/prompts/build-storefront.md
harness/codex/prompts/verify-readonly.md
```

From PowerShell, launch the foreground runners as background jobs:

```powershell
$root = (Resolve-Path '.').Path
$jobs = @(
  Start-Job -Name build-services -ArgumentList $root -ScriptBlock {
    param($root) Set-Location $root
    node scripts/codex-run.mjs run --id build-services --prompt-file harness/codex/prompts/build-services.md --sandbox workspace-write --effort high --label 'Build services'
  }
  Start-Job -Name build-storefront -ArgumentList $root -ScriptBlock {
    param($root) Set-Location $root
    node scripts/codex-run.mjs run --id build-storefront --prompt-file harness/codex/prompts/build-storefront.md --sandbox workspace-write --label 'Build storefront'
  }
  Start-Job -Name verify-readonly -ArgumentList $root -ScriptBlock {
    param($root) Set-Location $root
    node scripts/codex-run.mjs run --id verify-readonly --prompt-file harness/codex/prompts/verify-readonly.md --sandbox read-only --effort high --label 'Read-only verification'
  }
)
```

Poll the durable state, not the job output:

```powershell
node scripts/codex-run.mjs list
node scripts/codex-run.mjs last --id build-services
node scripts/codex-run.mjs last --id build-storefront
node scripts/codex-run.mjs last --id verify-readonly
$jobs | Wait-Job | Receive-Job
```

The Verify worker stays read-only while the two Build workers write. If two workers would
edit the same file, serialize them or put them in separate worktrees.

## CLI facts this guide relies on

Checked against the installed CLI (`codex-cli 0.146.0-alpha.3`). If an upgrade changes them,
`node scripts/harness-status.mjs` still finds the binary and the runner fails loudly rather
than silently dropping an argument.

- `codex exec [OPTIONS] [PROMPT]` reads the prompt from stdin when the prompt is `-`.
- `codex exec` accepts `--sandbox`, `--cd`, `--output-last-message`, `--color`,
  `--skip-git-repo-check`, `--json`, `--ephemeral`, `-c key=value`, `-m/--model`.
- `codex exec resume [SESSION_ID] [PROMPT]` accepts **neither `--sandbox` nor `--cd`, and not
  `--color` either**. The resumed turn keeps the session's conversation and its working root,
  because the root is part of the recorded session - but it does **not** keep the sandbox.
  Without an explicit override it starts with the CLI default, `workspace-write` and
  `approval: never`, so resuming a read-only Verify worker would silently hand it write
  access. `-c sandbox_mode="<mode>"` is the only channel that reaches the policy on resume,
  and the runner always passes it. Codex echoes the effective value as `sandbox: ...` in the
  banner it prints on start, which is how this was confirmed rather than assumed.
- `codex exec review` accepts `--uncommitted`, `--base <branch>`, `--commit <sha>` and
  `--output-last-message`.
- The CLI prints `session id: <uuid>` on stderr. That exact id is what `resume` uses.

## Cost

A Codex call is slow and token-heavy compared to a normal tool call: it runs a complete agent
loop. Do not fan out many calls in a loop. Batch the work into one well-specified prompt, or
use it where the independence buys something a subagent cannot - a different model family, or
an investigation whose detail should not enter this context.

See `.cursor/skills/codex-second-agent/SKILL.md` for the measured cost of the MCP transport,
the image generation path, and the network-isolation details.
