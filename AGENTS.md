# AGENTS.md — Project context for AI agents

> Single source of truth for how this repository is structured, built, and the
> conventions it follows. Read this before making changes. It wins over generic
> advice and over any framework rule that contradicts it.

## What Velmor is

A rights-verified marketplace platform. It discovers digital goods on the open
internet, decides whether each one may legally be resold, and only then offers it
for sale. Two products run on one core:

- **Velmor Rights** - B2B: given a good and its claimed license, return a
  defensible verdict on what a buyer may do with it.
- **Proofbasket** - B2C: the storefront over the goods that passed the gate.

This is not a catalogue and not a crawler. It is a rights decision with a shop
attached, and that ordering matters in every design: a good that cannot be
justified is not listed, even if it is popular.

## The one thing to internalise

The verdict is a pure function of its inputs, and nothing reaches the storefront
without `GateDecision.PUBLISHABLE`. If a change makes it possible to reason about
publishing with something non-deterministic, the change is wrong. See
`.cursor/rules/06-rights-engine.mdc`.

## Repository layout

```
velmor/                     composition root: CLI, container, agent adapters.
                            The only place that chooses concrete classes.
  cli.py                    typer entry point, env-file resolution, dispatch
  container.py              explicit wiring; async resources in an exit stack
  agents/                   ScoutAgent, AuditorAgent (CLI-facing adapters)

packages/core/              settings, environment, observability, fs guard, errors.
                            Imports nothing else from this repo.
packages/services/          domain models, rights engine, connectors, persistence,
                            LLM extraction, integrations. No agents here.
packages/scout/             discovery agent: find candidates (plain Python)
packages/auditor/           verification agent: build evidence, decide (LangGraph)
packages/api/               FastAPI surface (B2B verify, webhooks, health)

storefront/                 Next.js presentation layer; the scoped Node exception.
openspec/                   specs, active changes, config
.cursor/                    rules, commands, hooks, mcp.json, skills
.agents/skills/             installed skill collections (superpowers, langchain, ...)
scripts/setup-mcp.mjs       verify MCP servers resolve
```

## Tech stack

| Concern | Choice |
|---------|--------|
| Language | Python 3.13, uv workspace, hatchling |
| Lint / format | ruff (`line-length = 100`, rules adopted one at a time) |
| Tests | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |
| Data | Pydantic 2 models |
| Storage | PostgreSQL via SQLAlchemy 2.x async + asyncpg; Redis for queues |
| Checkpointing | `langgraph-checkpoint-postgres` (`AsyncPostgresSaver`) |
| Agent orchestration | LangGraph (branching, cycles, interrupts, resumable state) |
| Structured extraction | Pydantic AI (one extraction at a time) |
| Long-horizon research | DeepAgents (not used yet) |
| Tracing | Logfire + OpenInference instrumentors; Langfuse for LLM observability |
| Storefront | Saleor (planned) |
| Payments | Stripe (planned) |
| API | FastAPI + uvicorn (planned) |
| CLI | typer |

Python only in the product. Node exists for the agent harness and for
`storefront/`, the one deliberate exception: a presentation layer with no rights
logic, no payment secrets and no privileged Saleor credentials, and nothing
about publishing is decided there.

## How to run

```bash
uv sync
docker compose up -d
cp packages/scout/.env.example   packages/scout/.env.dev
cp packages/auditor/.env.example packages/auditor/.env.dev

uv run velmor --help
uv run velmor sources --env dev
uv run velmor run scout   --env dev
uv run velmor run auditor --env dev

uv run python -m pytest packages -q
uv run ruff check
```

Settings load from `.env.<profile>` per agent, resolved by `EnvFileResolver` in
`velmor/cli.py`: `packages/scout/.env.dev`, `packages/auditor/.env.dev` (profiles
`dev`, `stage`, `prod`, `test`). Every setting is required and raises
`ConfigurationError` at bootstrap when absent. There are no optional accessors and
no defaults, by design: a half-configured process must not start.

Full operational detail: `.cursor/skills/run-the-project/SKILL.md`.

## Architecture: the dependency direction is fixed

An arrow means "may import".

```
velmor/  (composition root: cli, container, agents/*)
   |
   v
packages/scout, packages/auditor      (agents: may import services + core)
   |
   v
packages/services                     (domain, rights, connectors, persistence)
   |
   v
packages/core                         (settings, environment, fs, errors)
```

- `packages/core` imports nothing from this repository except itself. It must not
  know that agents, rights, Saleor or LLMs exist.
- `packages/services` imports `packages/core` and nothing from the agents.
- An agent imports `packages/services` and `packages/core`. It must not import
  another agent.
- The composition root is the only place that knows about all of them.

Why the rights engine in particular must stay free of the agent stack: the
publication gate decides what the company may legally sell. If it can reach a model
or a framework, it becomes possible to reason about publishing with something
non-deterministic. Keeping it a pure function of its inputs is what makes a verdict
reproducible and auditable.

Enforced by `.cursor/rules/02-architecture-layers.mdc` and by
`packages/core/tests/unit/architecture/test_layering.py`, not only by this document.

## The rights contract (critical)

`Candidate` + `Evidence` -> `RightsResolver.resolve()` -> `RightsRecord` ->
`PublicationGate.decide()` -> `GateDecision`.

- **Deny by default.** An unrecognised license is `UNKNOWN`, and `UNKNOWN` is not
  publishable. `LicenseMatrix.resolve` returning `None` means not provable, never
  "probably fine".
- **No fuzzy matching.** If a string does not resolve to a canonical entry, it does
  not resolve. Never widen the alias table to make one item pass.
- **Reproducible.** No model, clock, randomness, network or filesystem read may
  influence a verdict. Time is passed in by the caller.
- **Models propose evidence, never verdicts.** A model may contribute an `Evidence`
  record; its output is never compared against an action to produce a decision.
- **The gate is the only door.** No bypass, not even for a free item. Every
  non-`PUBLISHABLE` decision carries at least one reason.
- **Append-only.** A correction is a new `RightsRecord` with a new timestamp and an
  author, never an edit of the old one.
- **`RightsResolver.ENGINE_VERSION`** is stamped into every record. Bump it in the
  same change whenever a verdict could change for identical inputs.

Vocabulary is fixed: `Candidate`, `Evidence`, `RightsVerdict`, `RightsAction`,
`LicenseGrant`, `GateDecision`, `StorefrontListing`, `VerificationOutcome`,
`VerificationRun`, `CandidateOutcome`, `CategoryRefusal`. Do not invent synonyms.

Full map: `.cursor/skills/rights-engine/SKILL.md`.

## Agent framework: pick the tool for the task

| Tool | Use it when | Do not use it when |
|------|-------------|--------------------|
| Plain Python | Decidable from inputs: policy, verdicts, gating, screening, discovery | Any judgement is needed |
| LangGraph | Control flow is a graph: branching, cycles, retries, interrupts | A straight line of calls would do |
| Pydantic AI | One structured extraction into a typed model | Multi-step orchestration |
| DeepAgents | Open-ended long-horizon research | The steps are known in advance |

Start at the top, move down only when the layer above provably cannot express the
requirement. As built: Scout is plain Python on purpose (a loop over queries and
connectors, no branching); Auditor is a LangGraph graph (it branches, loops on
investigation attempts, and interrupts for human review). The rights verdict path
is never an agent.

## Code conventions

- Standard Python style enforced by ruff: 100-column lines, sorted imports
  (`known-first-party = ["packages", "velmor"]`).
- Strict OOP: logic lives in class methods, not module-level functions. The only
  sanctioned module-level functions are typer callbacks and the console-script
  shim.
- Models are plain typed data containers: fields and no behaviour. No
  `@field_validator`, no `model_post_init`, no `require_*` helpers. Logic belongs in
  a service or a gate.
- Parameters and fields are required by default. A default exists only when the
  value is genuinely optional and the task says so.
- Prefer typed models over raw `dict` / `list`. Access `data[key]`, not
  `.get(key, default)`. Do not use truthiness to pick a default (`x or 0`).
- `try/except` is forbidden unless explicitly authorized and proven. See
  `.cursor/rules/03-error-handling.mdc`; it is canonical and is stricter than most
  guidance you have seen.
- Settings are read only through `SettingsLoader.required_*`. Do not add an
  optional accessor to make a missing value quiet.
- No `TODO` / `FIXME` unless asked. No compatibility shims, re-exports or
  transitional aliases: when moving code, update every caller and delete the old
  path.

## Current state

Implemented and tested:

- `packages/core`: settings, environment, `Observability`, `FsValidator`, errors.
- `packages/services`: domain models (including the pass report: `VerificationRun`,
  `CandidateOutcome`, `CategoryRefusal`), rights engine, screening, source registry
  and credential contract, connectors (`contract`, `factory`, `openverse`),
  persistence (`PostgresStore`, `InMemoryStore`, schema), Pydantic AI license
  interpreter.
- `packages/scout`: deterministic ingest job and runner.
- `packages/auditor`: graph state, node names, nodes, routing (including the
  escalation of a low-confidence reading), graph assembly, runner.
- `velmor`: CLI, container, agent adapters, the console pass report.
- The vertical slice is walkable end to end: Openverse discovery -> screening ->
  auditor graph -> gate decision -> `VerificationRun`. There is an integration-style
  path test that walks it with a fake connector, page fetch and interpreter, so no
  test needs a network, a model or a database.
- Tests: rights (`license_matrix`, `publication_gate`, `rights_resolver`),
  screening, source registry, discovery, every auditor node, routing, the pass
  report, the CLI report, and the architecture boundaries.

Scaffolded or not yet implemented - do not assume these work:

- `packages/services/src/saleor/` and `packages/services/src/payments/` are empty
  package placeholders. Saleor and Stripe integration is on the roadmap.
- `packages/api/src/routers/` is empty. The FastAPI surface is not built.
- Neither `velmor scout` nor `velmor auditor` has been run against a live source
  and a live database in this environment: the Postgres store and the checkpointer
  are exercised by no test, and the Openverse path is unproven end to end.
- A candidate that pauses for review has no verdict, so the next pass selects it
  again and repeats the fetch and the model call. That cost is reported as a
  "paused" outcome rather than hidden, and delivering the human ruling is not
  built.
- `packages/services` has no test for `PostgresStore`, `PageFetcher`, `ConnectorFactory`
  or the Openverse connector's payload mapping.
- DeepAgents is a declared dependency with no use yet.
- Type checking (`basedpyright`, `mypy`) is configured but is not a gate.
- `storefront/` is the scoped Node exception: a Next.js presentation layer outside
  the Python layering, with no rights logic and no payment secrets.

## Roadmap

1. Saleor: publish gate-approved goods to the storefront.
2. Stripe: payment and payout.
3. `packages/api`: B2B verify endpoint, Saleor/Stripe webhooks, health.
4. Human review, end to end: deliver a ruling into a resumed run instead of
   re-investigating the candidate on the next pass.
5. Docs: vision, architecture, rights engine, source catalogue.
6. Docker images, CI, and the remaining test coverage (`PostgresStore`, connectors,
   the API).

## AI tooling

### Skills

Installed with the `skills` CLI into `.agents/skills/` (Cursor reads this
directory), locked by `skills-lock.json`:

- **obra/superpowers** (14) - methodology: brainstorming, writing-plans,
  executing-plans, test-driven-development, systematic-debugging,
  verification-before-completion, requesting/receiving-code-review,
  subagent-driven-development, dispatching-parallel-agents, using-git-worktrees,
  finishing-a-development-branch.
- **langchain-ai/langchain-skills** (19) - `langgraph-*` (fundamentals,
  persistence, human-in-the-loop, cli), `langchain-*`, `deep-agents-*`,
  `ecosystem-primer`, `eval-engineering`, `swarm`. TypeScript variants were removed;
  there is no TypeScript here.
- **pydantic/skills** (3) - `pydantic`, `building-pydantic-ai-agents`,
  `logfire-instrumentation`.
- **langfuse/skills** (1) - `langfuse`.
- **0xdarkmatter/claude-mods** (1) - `python-pytest-ops`.

Project-authored skills live in `.cursor/skills/`:

| Skill | Covers |
|-------|--------|
| `run-the-project` | install, env files, CLI, tests, troubleshooting |
| `rights-engine` | the verdict path, the policy table, the invariants |
| `source-connector` | adding a source: spec, tier, credentials, connector, tests |
| `agent-graph` | LangGraph structure, nodes, state, interrupts, the LLM boundary |

Reinstall or update:

```bash
npx skills add obra/superpowers --skill '*' -a cursor --copy -y
npx skills add langchain-ai/langchain-skills --skill '*' -a cursor --copy -y
npx skills add pydantic/skills --skill '*' -a cursor --copy -y
```

### MCP servers (`.cursor/mcp.json`)

| Server | Source | Auth / prerequisite |
|--------|--------|---------------------|
| context7 | `@upstash/context7-mcp` | none - library docs, use before coding against an API |
| sequential-thinking | `@modelcontextprotocol/server-sequential-thinking` | none |
| langfuse-docs | remote `https://langfuse.com/api/mcp` | none |
| postgres | `uvx postgres-mcp --access-mode=restricted` | read-only; `DATABASE_URI` in the config points at the local dev database |
| redis | `uvx redis-mcp-server@latest` | none for local Redis |
| github | remote `https://api.githubcopilot.com/mcp/` | `GITHUB_PERSONAL_ACCESS_TOKEN` |
| stripe | remote `https://mcp.stripe.com` | OAuth |
| playwright | `@playwright/mcp` | none |

`GITHUB_PERSONAL_ACCESS_TOKEN` is interpolated with `${env:...}`; it is not stored
in the config. Keep secrets out of `.cursor/mcp.json`; use `${env:VAR}`.

Verify a fresh checkout resolves every server:

```bash
node scripts/setup-mcp.mjs
```

### Rules (`.cursor/rules/`)

| Rule | Governs |
|------|---------|
| `00-project-rules.mdc` | response style, honesty about state, scope discipline |
| `01-security-secrets.mdc` | secrets handling, credential scope, git safety |
| `02-architecture-layers.mdc` | object lifetime and the fixed import direction |
| `03-error-handling.mdc` | `try/except` is forbidden unless authorized and proven |
| `04-python.mdc` | Python style, models, parameters, logging, comments |
| `05-agent-graphs.mdc` | framework choice, LangGraph state/nodes/edges/interrupts |
| `06-rights-engine.mdc` | deny by default, evidence, the gate, policy changes |

### Hooks (`.cursor/hooks.json`)

| Hook | Event | Effect |
|------|-------|--------|
| `secret-guard.cjs` | preToolUse on writes | denies a write containing a hardcoded credential (`.env` exempt) |
| `policy-guard.cjs` | preToolUse on writes | requires human approval for rights policy files and for harness files |
| `destructive-guard.cjs` | beforeShellExecution | denies force-push to main/master, `reset --hard`, `clean -fd`, `docker ... -v`, `dropdb`, recursive force deletes |
| `lint-feedback.cjs` | postToolUse on writes | runs `ruff check` on the edited file and returns violations as context |

Hooks are enforcement, not suggestions. Do not work around a hook; if a blocked
operation is genuinely required, ask the user to run it.

### Commands (`.cursor/commands/`)

| Command | Purpose |
|---------|---------|
| `/ship <task>` | autonomous orchestrator: propose -> implement (fresh implementer subagent per task, task review, bounded fix loop) -> verify (evidence) -> `/rights-verify` -> `/review` -> finish -> archive. Stops for the human only at plan approval and integration. |
| `/review` | dispatches `bugbot` + `security-review` as the merge gate; reports PASS / CHANGES REQUIRED |
| `/rights-verify` | domain runtime verifier: proves the publication gate still refuses what it must |
| `/opsx-*` | OpenSpec: explore, propose, apply, sync, update, archive |

### Writer/reviewer roles - invoke, do not reimplement

| Role | Tool |
|------|------|
| Writer | fresh `generalPurpose` subagent per task (`subagent-driven-development/implementer-prompt.md`) |
| Task checker | task reviewer subagent (`task-reviewer-prompt.md`) |
| Final checker | `bugbot` + `security-review` subagents |
| Domain runtime checker | `/rights-verify` |
| Policy enforcer | hooks `secret-guard` / `policy-guard` / `destructive-guard` (automatic) |
| Contract | OpenSpec specs + `/opsx-*` |
| Evidence | `verification-before-completion` |
| Integration | `finishing-a-development-branch` |

### Contract: OpenSpec

`openspec/config.yaml` carries the project context and the rules for `proposal`,
`specs`, `design`, `tasks`, `apply` and `archive`. Specs in `openspec/specs/` are
the product contract; the code conforms to them, not the other way around.

## Quality gates

Before claiming work is done, run and quote the output of:

```bash
uv run ruff check
uv run python -m pytest packages -q
uv run python -m compileall -q packages velmor
openspec validate --strict "<change>"     # when specs or planning changed
```

And for anything touching rights, screening, connectors or the gate: `/rights-verify`.
For the final gate before merge: `/review`.

Never claim a check passed without its output. Never describe what should happen as
though it did. If something is unverified, say it is unverified.

## Working rules for agents

- Preserve the rights contract. It is the product, not an implementation detail.
- Make the smallest change that satisfies the task. Do not refactor neighbours or
  "clean up while here".
- Do not add a dependency without explicit approval.
- Never commit secrets; use `.env` / `.env.example`.
- Keep commands and scripts cross-platform (the environment is Windows/PowerShell).
- Do not rewrite git history, force-push main/master, or run destructive
  git/docker commands.
- Follow the installed `superpowers` methodology for planning, debugging and
  verification.
- Use `/ship` for end-to-end autonomous work and `/review` as the merge gate. The
  reviewer agents and the policy hooks are the enforcement layer; do not bypass
  them.
- When a task turns out to need the rights rules to bend to pass, stop. That is a
  signal the design is wrong, not that the rule is negotiable.
