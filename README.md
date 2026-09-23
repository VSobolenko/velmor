# Velmor — rights-verified marketplace platform

Velmor discovers digital goods across the open internet, decides whether each one
may legally be resold, and publishes only the ones it can prove.

Two products run over one core:

| Product | Audience | What is sold |
|---------|----------|--------------|
| **Velmor Rights** | B2B | A verdict on usage and resale rights, with an audit trail |
| **Proofbasket** | B2C | The goods in the catalog that passed that verdict |

The same rights engine powers both: for B2B it *is* the product, for the storefront
it is the publication gate. One component, two monetizations.

## The core principle

Crawling is cheap. Staying legal is what is hard. So:

> **Deny by default, allow by whitelist.**

A good is published only when every condition is provably satisfied. Anything else
is refused, not queued. That strictness is what makes the pipeline automatic: it is
the safety mechanism, and its price is catalog size.

The verdict is a pure function of its inputs, and no model, clock or network call
may influence it. A model may propose evidence; it never returns a verdict.

## What this project is not

- It is not a scraper of other marketplaces. Listing scraping without a contract is
  out of scope.
- It does not sell goods whose rights are merely *plausible*. A license field that
  says `MIT` is a claim, not a proof.
- It does not trade in keys, accounts or subscriptions. Those are prohibited by
  every payment provider's terms and are blocked in the source registry.

## Repository layout

```
velmor/                     composition root: CLI, container, agent adapters
packages/
  core/                     bootstrap, settings, observability, fs guard, errors
  services/                 domain models, rights engine, connectors, commerce, persistence
  scout/                    agent: discovers candidate goods (plain Python)
  auditor/                  agent: verifies rights, decides (LangGraph)
  api/                      FastAPI commerce surface (catalogue, checkout, account, webhooks, downloads)
storefront/                 Next.js Proofbasket UI; presentation only
openspec/                   spec-driven change contracts (proposal -> tasks -> archive)
.agents/skills/             installed skill collections
.cursor/                    rules, hooks, commands, skills, MCP config
scripts/setup-mcp.mjs       verify every MCP server resolves on this machine
```

## Stack

| Concern | Choice |
|---------|--------|
| Language / runtime | Python 3.13, `uv` workspace, hatchling |
| Lint / format / tests | ruff, pytest + pytest-asyncio |
| Data models | Pydantic 2 |
| Storage | PostgreSQL (SQLAlchemy 2.x async + asyncpg) + Redis |
| Checkpointing | `langgraph-checkpoint-postgres` |
| Agents | LangGraph for graph control flow, Pydantic AI for one extraction at a time, DeepAgents for long-horizon research (not used yet) |
| Observability | Logfire traces, OpenInference instrumentors, Langfuse for LLM observability |
| CLI | typer |
| Storefront | Saleor GraphQL via `httpx`, behind a Next.js Proofbasket UI (`storefront/`) |
| Payments | Stripe and bePaid; checkout re-verifies the gate outcome at payment time |

Wiring is explicit in `velmor/container.py`. There is no dependency-injection
framework: every dependency is a plain constructor argument, so reading that file
is enough to learn what a process is made of.

## Status

Implemented: the rights engine (with tests), domain models, screening, source
registry and credentials, the Openverse connector, persistence, the Pydantic AI
license interpreter, the scout ingest job, the auditor graph with its nodes and
routing, the CLI and the container. On top of that, the commerce layer: catalogue
entries and presentations, categories, publication to Saleor, entitlements and
orders, payment providers with payment-time re-verification, downloads behind
short-lived grants, the FastAPI commerce surface, and the Next.js storefront.

The vertical slice is walkable end to end: discovery selects candidates, screening
removes prohibited goods, the graph verifies the rest, the gate decides, the good is
published, and a buyer can browse, pay and download it. A demo deployment runs at
`https://shop.78-111-89-46.sslip.io/`.

Not yet implemented: live Stripe and bePaid credentials and production
legal-entity disclosure (demo and stub paths are what is proven), delivering a
human ruling back into a paused run, the B2B verify API as the main surface,
category curation of the whole catalogue, and type checking as a gate. `AGENTS.md`
states the exact position, and `HANDOFF.md` records what is in flight right now.

The catalogue is currently small and its categories are partly curated; the rights
gate is the reason, and that is the intended trade.

## Setup

```bash
uv sync
docker compose up -d
cp packages/scout/.env.example   packages/scout/.env.dev
cp packages/auditor/.env.example packages/auditor/.env.dev
```

Env files live per agent: `packages/<agent>/.env.<profile>`, resolved by
`EnvFileResolver` (`dev`, `stage`, `prod`, `test`). Every variable is required and
a missing one raises `ConfigurationError` at bootstrap rather than falling back to
a default: a half-configured process must not start.

## Run

```bash
uv run velmor --help
uv run velmor sources --env dev
uv run velmor run scout   --env dev
uv run velmor run auditor --env dev
uv run velmor publish --env dev
uv run velmor serve --env dev
uv run velmor curate --model <provider:model> --env dev --apply
uv run velmor cover list --env dev
```

`velmor curate` is the one operator command that calls a model: it proposes the
display title, the summary and the category of each good, and it refuses to run
without `--apply`. It loads the API profile, so that profile needs the model
credential. `HANDOFF.md` records how it is supplied on the demo host.

## Test and lint

```bash
uv run python -m pytest packages velmor -q   # integration and eval markers deselected
uv run ruff check
uv run ruff format
uv run python -m compileall -q packages velmor
```

## Agent harness

| Goal | Command |
|------|---------|
| End-to-end autonomous work | `/ship <task>` |
| Review gate (bugs + security) | `/review` |
| Prove the publication gate still refuses what it must | `/rights-verify` |
| Prove a buyer can see, understand and buy, in every locale | `/ux-verify` |
| Plan a change (OpenSpec) | `/opsx-propose <task>` |
| Implement a change | `/opsx-apply` |
| Archive a finished change | `/opsx-archive` |

Start with `AGENTS.md`. It is the single source of truth for structure,
conventions and the working rules an agent must follow. `.cursor/rules/*.mdc` are
the normative rules, `.cursor/skills/` holds the project skills
(`run-the-project`, `rights-engine`, `source-connector`, `agent-graph`,
`storefront-ux`), and `openspec/config.yaml` carries the project context OpenSpec
shows to the writer.

Anything a buyer reads or acts on is specified by what the buyer sees, not only by
what the system does: `.cursor/rules/07-product-surface.mdc` is normative there, and
a change to such a surface is verified by looking at it, with a screenshot as the
evidence.

## Security

Never commit secrets. Every credential belongs in `.env.<profile>` (git-ignored);
`.env.example` carries placeholders only. Three hooks enforce this and the git
safety rules automatically: `secret-guard.cjs`, `policy-guard.cjs` (human approval
for the rights policy surface and the harness itself) and `destructive-guard.cjs`.

## License

Proprietary. All rights reserved.
