---
name: run-the-project
description: How to run, test, lint and operate Velmor from a clean checkout - install, env files per agent, CLI commands, database, tests, and the harness tooling.
disable-model-invocation: true
---

# run-the-project

Operational reference for Velmor. Load this when the user asks "how do I run X",
when a command fails, or before touching docker/env/CI.

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | 3.13 | `requires-python = ">=3.13,<3.14"` |
| uv | current | workspace, dependency resolution, running everything |
| Docker | current | local Postgres + Redis |
| Node | 20+ | the agent harness: hooks, `scripts/*.mjs`, and `storefront/` has its own toolchain |

Python only in the product. Node exists for the agent harness and for
`storefront/`, the scoped Node exception: a presentation layer with no rights
logic, no payment secrets and no privileged Saleor credentials, and nothing
about publishing is decided there.

## First run

```bash
uv sync                                  # resolve and install the workspace
docker compose up -d                     # Postgres on 5432, Redis on 6379
```

## Environment files

Settings are read from `.env.<profile>` files, **per agent**, resolved by
`EnvFileResolver` in `velmor/cli.py`:

| Agent | File | Root |
|-------|------|------|
| scout | `packages/scout/.env.dev` | `packages/scout` |
| auditor | `packages/auditor/.env.dev` | `packages/auditor` |

Profiles come from `Environment` (`packages/core/src/bootstrap/environment.py`):
`dev`, `stage`, `prod`, `test`. So `.env.dev`, `.env.stage`, `.env.prod`,
`.env.test`.

```bash
cp packages/scout/.env.example   packages/scout/.env.dev
cp packages/auditor/.env.example packages/auditor/.env.dev
```

`.env.example` is committed; `.env.*` is git-ignored. Never put a real credential
in a file that is committed; `secret-guard.cjs` will block the write.

Required by every process (`PlatformSettings`): `ENVIRONMENT`, `DATABASE_URL`,
`REDIS_URL`, `LOGFIRE_TOKEN`.
Scout adds: `SCOUT_QUERIES`, `SCOUT_PAGE_LIMIT`, `SCOUT_INTERVAL_SECONDS`,
`SCOUT_CONCURRENCY`.
Auditor adds: `AUDITOR_MODEL`, `AUDITOR_MAX_INVESTIGATION_ATTEMPTS`,
`AUDITOR_ESCALATION_CONFIDENCE`, `AUDITOR_BATCH_SIZE`, `AUDITOR_INTERVAL_SECONDS`,
`OPENAI_API_KEY`.

Every setting is required. A missing variable raises `ConfigurationError` at
bootstrap (`SettingsLoader._read`), by design: a half-configured process must not
start. Do not add an optional accessor to silence it.

## Run

```bash
uv run velmor --help
uv run velmor sources --env dev                     # list sources, tier, enabled
uv run velmor run scout --env dev                   # one discovery pass
uv run velmor run scout --env dev --command once
uv run velmor run auditor --env dev                 # one verification pass, then the report
uv run python -m velmor run scout -e dev            # equivalent
```

A verification pass prints one line per candidate with its outcome - published,
refused, screened out or paused - and a count of refusals per prohibited category,
so a pass that published nothing explains itself instead of looking empty.

`velmor` is the console script (`[project.scripts] velmor = "velmor.cli:main"`).
The CLI is a thin shim: it resolves the env file, builds the `Container`, and
delegates. All logic is in the agent classes under `velmor/agents/`.

## Test and lint

```bash
uv run python -m pytest packages velmor -q           # unit tests, integration/eval deselected
uv run python -m pytest packages velmor -q -m integration  # only when asked
uv run python -m pytest packages velmor -q -m eval   # needs a live model
uv run ruff check                                   # lint
uv run ruff format                                  # format
uv run python -m compileall -q packages velmor      # import sanity
```

`pyproject.toml` sets `addopts = "-m 'not integration and not eval'"`, so a plain
pytest run never touches the network or an LLM. `testpaths = ["packages", "velmor"]`.

Type checking (`basedpyright`, `mypy`) is configured but is **not** a gate yet.

## Harness tooling

```bash
node scripts/harness-status.mjs  # is the harness complete and consistent on this machine
node scripts/selftest.mjs        # do the harness scripts honour their own contracts
node scripts/setup-mcp.mjs       # what each MCP alias resolves to, and what needs a value
node scripts/codex-run.mjs list  # durable Codex workers and their state
openspec list                    # OpenSpec changes
openspec validate --strict "<change>"
```

`harness-status.mjs` reports `PASS` / `WARN` / `INFO` / `FAIL` and exits non-zero on a
`FAIL`. A `WARN` is a machine-level gap (no Docker, no Codex CLI), not a repository defect.
The detail behind every surface is in `harness/`.

## OpenSpec workflow

```bash
/opsx-explore                   # think before proposing
/opsx-propose <task>            # proposal + specs + design + tasks
/opsx-apply                     # implement the tasks
/opsx-sync                      # push delta specs into openspec/specs
/opsx-archive                   # close the change after review
```

## Commands

| Command | Purpose |
|---------|---------|
| `/ship <task>` | End-to-end autonomous run with two human checkpoints |
| `/eval` | Independent Evaluator grading against a fixed rubric |
| `/review` | Dispatch `bugbot` + `security-review` as a merge gate |
| `/rights-verify` | Prove the publication gate still refuses what it must |
| `/ux-verify` | Drive the running shop; screenshots are the evidence |
| `/harness-status` | Is the harness complete and consistent on this machine |
| `/diagnose` | Root cause of a harness, tooling or agent failure |
| `/improve-harness` | Turn a repeated failure into a rule, hook or sensor |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ConfigurationError: Required environment variable 'X' is not set` | missing key in the agent's `.env.<profile>` | add it; do not add a default |
| `FileNotFoundError: Environment file not found` | `packages/<agent>/.env.<profile>` does not exist | copy from `.env.example` |
| `SourceNotConfiguredError` | an `enabled` source lacks its `required_env` keys | add the keys or set `enabled=False` |
| `AsyncPostgresSaver` / connection errors | Postgres not up | `docker compose up -d` |
| `RuntimeError: Container is not entered` | used a resource outside `async with Container(...)` | enter the container first |
| hook blocks a write | `secret-guard` or `policy-guard` fired | fix the secret, or get human approval for a policy file |
| `destructive-guard` blocks a command | irreversible git/docker command | do not work around it; ask the user to run it |
