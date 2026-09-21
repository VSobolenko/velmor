---
name: codex-second-agent
description: Delegate work to Codex (a GPT-based agent) as an independent second agent - review, implementation, research, image generation - through the `codex` MCP tools or the `codex` CLI. Use when you need genuine model diversity, a second opinion, or to offload a large independent investigation.
disable-model-invocation: true
---

# Codex as a second agent

Codex is a full agent harness (its own loop, tools, sandbox, context window) running
OpenAI models. In this repo it is wired up as an MCP server, so it can be dispatched to
like any other tool.

## Why use it at all

**Model diversity is the point.** Subagents spawned here inherit *this* model, so they
share its blind spots - a reviewer that thinks like the author tends to miss the same
things. Codex runs a different model family, so its failure modes are uncorrelated with
ours. That makes it the strongest available second opinion for review work.

Secondary reasons:

- **Independent context** - a large investigation consumes Codex's context, not ours.
- **Stateful** - `threadId` holds a multi-turn conversation (`codex-reply`).
- **Image generation** - its built-in `image_gen` tool needs no `OPENAI_API_KEY`. This
  is the only image generator wired up for this repo.

## What Codex knows automatically (measured in the reference project)

- **Codex auto-reads the root `AGENTS.md`.** Conventions in that file reach it without
  any prompting. This is the free channel, and for this repo it matters more than usual:
  `AGENTS.md` carries the dependency direction, the rights contract, the Python style
  and the `try/except` prohibition.
- **Codex does NOT auto-read** `.cursor/rules/*.mdc`, `.agents/skills/**`, or
  `openspec/specs/**`. Those are Cursor-side conventions. If a rule must bind Codex and
  it lives only in a `.mdc` file, restate it in the prompt or in
  `developer-instructions`.
- **`developer-instructions` is honoured.** It is delivered as a developer-role message,
  so it outranks the user prompt. Use it for constraints that are not already in
  `AGENTS.md`.

Consequence: `AGENTS.md` is the single channel that reaches Codex for free. If a
convention must bind an external agent, it belongs in `AGENTS.md`, not only in a `.mdc`.

## Non-negotiable: the rights contract

This overrides every other instruction in this skill. Codex must never be asked, and
must never be allowed, to do any of the following to make a test or an item pass:

- Weaken `PublicationGate` - no bypass, no widened evidence kinds, no removed condition.
- Widen `LicenseMatrix.ALIASES` so an unrecognised string resolves. `None` means "not
  provable", never "probably fine".
- Let a model produce a verdict. A model contributes `Evidence`; it never decides.
- Wrap the gate or a rights call in `try/except` to swallow a refusal.
- Edit `packages/services/src/rights/**` at all without an explicit human request.

When a task appears to need the rights rules to bend in order to pass, stop. That is a
signal the design is wrong, not that the rule is negotiable. Report it instead.

## Accountability protocol (mandatory)

Codex is launched here, so its output is answered for here. Codex's self-report is
**never** evidence. Run these four steps on every delegation that produces code.

### 1. Prevent

- Conventions that belong in `AGENTS.md` must be there - that is the free channel.
- Anything else (task-specific constraints, a narrower scope than the repo default) goes
  in `developer-instructions`, not buried in the middle of a long prompt.

### 2. Contain

- Writing work goes into a **separate git worktree** (`using-git-worktrees`), so a bad
  result can be discarded without touching the working tree.
- Read-only work stays on `sandbox: "read-only"` against the main tree.

### 3. Verify - objective, tool-based

This repo has no changed-files-only script; the gates are run directly.

```bash
uv run ruff check                          # style over the whole repo, fast
uv run python -m compileall -q packages velmor   # syntax
uv run python -m pytest packages velmor -q       # behaviour and contracts
```

`ruff check` passes on the current tree, so a failure is attributable to the change. Read
the diff as well: these gates prove style, syntax and covered behaviour. They cannot tell
you the logic is wrong, that a verdict changed for identical inputs, or that
`RightsResolver.ENGINE_VERSION` should have been bumped. That judgement is ours.

Any change touching rights, screening, connectors or the gate also requires
`/rights-verify` before it is called done.

### 4. Reject and correct

On a violation, reply on the **same thread** with `codex-reply` - do not start a new
session. Give the exact violation from the tool, not a vague "it's wrong":

```
codex-reply({
  threadId: "<id>",
  prompt: `ruff rejects your change. Fix exactly these and nothing else:
  - packages/services/src/rights/license_matrix.py:23 - line too long (104 > 100)
  Re-run \`uv run ruff check\` before reporting done.`
})
```

Re-verify after it answers. Loop until the gate is green, then still read the diff.

## The two MCP tools

### `codex` - start a session

Required: `prompt`. Returns `{ threadId, content }`.

| Parameter | Values | Notes |
|---|---|---|
| `prompt` | string | **Required.** The initial user prompt. |
| `cwd` | string | Working directory. Relative paths resolve against the MCP server's cwd. |
| `sandbox` | `read-only` \| `workspace-write` \| `danger-full-access` | Default is Codex's own config. **Set this explicitly, always.** |
| `approval-policy` | `untrusted` \| `on-request` \| `never` | Whether Codex must ask before running generated shell commands. |
| `model` | e.g. `gpt-5.6-terra` | Optional override. |
| `config` | object | Per-call overrides of `~/.codex/config.toml`. |
| `base-instructions` | string | Replaces Codex's default system instructions entirely. |
| `developer-instructions` | string | Injected as a developer-role message (prefer this over `base-instructions`). |
| `compact-prompt` | string | Prompt used when compacting the conversation. |

### `codex-reply` - continue a session

Required: `prompt`, plus the `threadId` returned by the first call. Returns
`{ threadId, content }`.

## Models

Slugs as documented in the reference project; list what the installed binary offers
before relying on one.

| Slug | Description |
|---|---|
| `gpt-5.6-terra` | Balanced agentic coding model. Default reasoning: medium. |
| `gpt-5.6-sol` | Reliable agentic workhorse. Default reasoning: low. |
| `gpt-5.6-luna` | Fast and affordable agentic coding model. |
| `gpt-5.5` | Previous generation. |
| `codex-auto-review` | **Not for code review** - decides whether to auto-approve commands. |

Pick `gpt-5.6-luna` for cheap mechanical work, `gpt-5.6-terra` for judgement work,
`gpt-5.6-sol` for long autonomous runs.

## Safety rules

1. **Always set `sandbox` explicitly.** Default to `read-only` for review, research and
   analysis. Use `workspace-write` only when Codex must produce files.
2. **Never combine `sandbox: "danger-full-access"` with `approval-policy: "never"`** on
   an unattended run. That is an unrestricted agent with no guardrails.
3. This project is registered as `trust_level = "trusted"` in `~/.codex/config.toml`, with
   `[windows] sandbox = "elevated"`. Codex **can** run shell commands and modify the repo.
   Treat it as a peer developer, not a sandboxed function call.
4. **Never accept a Codex change without an objective check.** Its "done", its
   self-reported test results and its summary are all claims. This is the single most
   important rule here: what it produces is our responsibility.
5. Never commit, merge, push or archive on Codex's word. The human checkpoint applies to
   its work exactly as it does to ours.
6. `secret-guard.cjs` only guards *our* writes. **Codex writing a secret is not
   intercepted** - the hook never sees its tool calls. Read its output before staging.
   Never let it write `packages/*/.env.*` or anything under `~/.codex`.

## Concurrency hazard

Two agents editing one worktree will clobber each other. Before delegating writing work,
isolate it:

- Run `codex` with `cwd` pointed at a **separate git worktree**, or
- Keep Codex on `read-only` while we edit.

Concurrent *read-only* review against the same worktree is safe.

## Delegation patterns

### 1. Independent reviewer - highest-value use

Run it *alongside* our own review, not instead of it. Keep it read-only.

```
codex({
  sandbox: "read-only",
  cwd: "<repo root>",
  model: "gpt-5.6-terra",
  prompt: `You are an independent reviewer. Read AGENTS.md first, then
  .cursor/rules/02-architecture-layers.mdc, 03-error-handling.mdc and
  .cursor/rules/06-rights-engine.mdc, and .cursor/skills/rights-engine/SKILL.md.

  Review the uncommitted changes (git status, git diff).

  Report ONLY blocking findings, each as file:line, what is wrong, why it matters.
  Check specifically for:
  - the publication gate being weakened, bypassed or wrapped in try/except
  - a model contributing a verdict rather than evidence
  - an alias or prefix added to LicenseMatrix.ALIASES
  - an import that violates the fixed dependency direction
  - rights/** changed without an explicit request
  - missing ENGINE_VERSION bump when a verdict could change for identical inputs

  Do not modify any files. If you find nothing blocking, say so plainly.`
})
```

### 2. Implementer in an isolated worktree

Always pair a writing delegation with a worktree and a verification pass.

```
codex({
  sandbox: "workspace-write",
  approval-policy: "on-request",
  cwd: "<worktree path>",
  model: "gpt-5.6-sol",
  developer-instructions: `This repository is Python 3.13, uv workspace, ruff with
  line-length 100. Strict OOP: logic lives in class methods, not module-level
  functions. Models are plain typed data containers - no validators, no helpers.
  try/except is FORBIDDEN unless the human explicitly authorised it in this task.
  No emoji. No compatibility shims, re-exports or transitional aliases. See AGENTS.md.`,
  prompt: `Read AGENTS.md first - it is authoritative.

  Task: <task>.
  Run \`uv run ruff check\` and \`uv run python -m pytest packages velmor -q\` before
  reporting done, and include the raw output in your report.`
})
```

Then verify independently - never take its "done" at face value.

### 3. Large independent investigation

Use `read-only`. Ask for a **structured** answer so the result stays compact in our
context. Example: "map every place `declared_license_id` is read, grouped by module,
each with file:line" - one call, and its exploration never touches our context.

### 4. Multi-turn collaboration

Use the returned `threadId` with `codex-reply` to push back, ask follow-ups, or have it
revise. This is the difference between a one-shot tool and a real collaborator - use it
when its first answer is wrong but close.

### 5. Image generation

```
codex({
  sandbox: "workspace-write",
  cwd: "<repo root>",
  prompt: `Use your imagegen skill and built-in image_gen tool to generate
  <description>. Save the final PNG into <workspace path> and reply with the
  absolute path only.`
})
```

Notes:

- The built-in `image_gen` tool requires **no** `OPENAI_API_KEY`.
- Codex saves to `$CODEX_HOME/generated_images/...` by default; ask it to copy into the
  workspace, or the asset is not in the repo.
- Measured in the reference project: ~52 s and ~11.5k tokens for one 1254x1254 PNG. It is
  slow.

## Network access - measured in the reference project, and it is NOT what you'd expect

Verified on this machine (Windows, `~/.codex/config.toml` -> `[windows] sandbox = "elevated"`):

| Path | Result |
|---|---|
| Shell command egress (default) | **BLOCKED** |
| + `config: {sandbox_workspace_write: {network_access: true}}` | **BLOCKED** |
| + `config: {features: {network_proxy: true}}` | **BLOCKED** |
| Built-in web search | **UNAVAILABLE** - `search_tool` is removed |
| Browser tool | **UNAVAILABLE** in an MCP-server session |
| Codex's own model calls | **WORK** - it answers |
| Built-in `image_gen` | **WORKS** |
| Our own shell | **Has full internet** |

So the precise statement is: **the Codex process is online, but every command it runs is
network-isolated, and it has no search or browser tool.** It cannot fetch live information
from the internet. Do not delegate anything that needs it.

Consequences:

- **Never let it fetch URLs, install packages, or call web APIs.** Have it work from what
  is already in the repo, or fetch the data ourselves and pass it in the prompt. For this
  repo that means: no `uv sync`, no `docker`, no `pip install`, no database access.
- **Network attempts can hang for many minutes** because Codex retries. If a task might
  touch the network, say "run exactly one command, do not retry, stop immediately on
  failure".

## Multi-turn sessions are process-scoped

`codex-reply` only finds a `threadId` **within the same MCP server process**. It works
throughout a Cursor session, because Cursor keeps the MCP server alive. It does not work
across separate one-shot CLI spawns; there, each invocation is a new process.
Persisted sessions resume with `codex resume` / `codex exec resume`, a separate mechanism.

## Measuring cost

Codex calls are **slow and token-heavy** compared to a normal tool call. Measured in the
reference project on this machine:

- Trivial prompt: **~14 s**, ~18.5k input tokens.
- Current time via shell: **~37 s**.
- One image generation: **~52 s**, ~11.5k tokens.
- Repository-wide brand audit (28 findings, 19 files): **~105 s**.
- **Worst observed: ~14 minutes** - a network-touching task that retried until killed.

Do not fan out many Codex calls in a loop. Batch the work into one well-specified prompt,
or use it where its independence actually buys something.

## CLI fallback

If the MCP server is unavailable, drive the same agent through the shell. The binary lives
inside a versioned editor extension, so it is usually **not** on `PATH`. Resolve it
through the launcher:

```bash
node .cursor/mcp/codex-launcher.cjs exec -s read-only -C "<dir>" "<prompt>"
```

Useful flags: `-s/--sandbox`, `-C/--cd`, `-m/--model`, `--json` (JSONL events),
`-o/--output-last-message <file>`, `-i/--image <file>`, `--skip-git-repo-check`.

## Setup in this repo

`.cursor/mcp.json` registers the server as:

```json
"codex": {
  "command": "node",
  "args": ["${workspaceFolder}/.cursor/mcp/codex-launcher.cjs", "mcp-server"]
}
```

Two deliberate choices, both inherited from the reference project:

- **`${workspaceFolder}` interpolation**, not a relative path. Cursor documents
  `${workspaceFolder}` as "the folder that contains `.cursor/mcp.json`". Relative paths in
  `args` have an **undocumented** resolution base, so relying on them is a guess.
- **A launcher script**, because the Codex binary lives inside a *versioned* extension
  directory. Hardcoding the version would break the server on every extension update. The
  launcher re-resolves it on each start, and is deliberately cwd-independent: it discovers
  the binary via the Windows registry, the paths of running editor processes, and
  well-known per-user extension roots.

`~/.codex/config.toml` registers `d:\python\velmor` as `trust_level = "trusted"`, the same
setting the reference project uses.

## Verifying the integration

```bash
# Should print the two tools: `codex` and `codex-reply`.
node .cursor/mcp/codex-launcher.cjs mcp-server

# Show which binary was resolved. Run this first whenever the server fails to start.
CODEX_LAUNCHER_DEBUG=1 node .cursor/mcp/codex-launcher.cjs mcp-server
```

Measured in this repo: `node .cursor/mcp/codex-launcher.cjs --version` resolves
`codex.exe` from the VS Code extension directory and prints `codex-cli 0.146.0-alpha.3`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `could not locate the Codex binary` | The Codex/ChatGPT extension is not installed in any editor the launcher can see. Install it, or set `CODEX_BIN` to the full path of the executable. |
| Server starts but no `codex` tool appears | The MCP server list is read at startup - reload the Cursor window and enable the server in Settings -> MCP. |
| Worked yesterday, dead today | The extension auto-updated. This is exactly what the launcher exists to absorb - run the debug command above; if it still fails, the extension layout changed and `PLATFORM_SUBPATHS` needs updating. |
| Calls hang for minutes | Expected. Codex runs a full agent loop (measured 14 s - 105 s). It is not a fast tool call. |
| It reports it ran the tests | Not evidence. Run `uv run python -m pytest packages velmor -q` ourselves. |

Override the binary explicitly with `CODEX_BIN` when testing a non-standard install.

## Quick decision table

| Situation | Use Codex? |
|---|---|
| Need an independent review from a different model family | **Yes** - strongest case |
| Bounded mechanical edit where our conventions matter | No - use a subagent; it inherits the rules |
| Need to produce a raster image | **Yes** - it is the only generator wired up |
| Large investigation whose detail should not enter our context | **Yes** |
| Disagreement with its first answer | **Yes** - `codex-reply` on the same thread |
| Needs live data from the internet | **No** - egress is blocked and search is removed |
| Anything touching the rights contract | **No** - not without an explicit human request |
