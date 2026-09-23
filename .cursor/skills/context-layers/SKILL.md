---
name: context-layers
description: How much to load at each stage of work in Velmor, and what to do when the context fills up. Use at session start and when moving between stages of /ship.
---

# Context layers

Loading everything is the most common way to make an agent worse: the contract that matters
gets diluted by detail that does not, and the window fills before the work starts.

| Layer | When | Load |
|-------|------|------|
| **L1** | Every session | `AGENTS.md` (already always-on), plus the injected harness orientation from `session-start.cjs` |
| **L2** | The active stage | Exactly the skills that stage names, and nothing else |
| **L3** | On demand | Spec detail, research, a file read, a worker's output |

## L2, by stage

| Stage | Load |
|-------|------|
| Plan (`/opsx-propose`) | `openspec-propose`, `writing-plans`, the specs in `openspec/specs/` that the change touches |
| Rights work | `rights-engine`, `.cursor/rules/06-rights-engine.mdc` |
| A new discovery source | `source-connector` |
| Agent graph work | `agent-graph`, the relevant `langgraph-*` skill, `.cursor/rules/05-agent-graphs.mdc` |
| Structured extraction | `building-pydantic-ai-agents` |
| Buyer surface | `storefront-ux`, `.cursor/rules/07-product-surface.mdc` |
| Review (`/review`, `/eval`) | The diff, the specs, `.cursor/rules/`, `/eval` |
| Harness work | `harness/README.md`, `harness/cursor-surface.md`, `/improve-harness` |
| Any failure | `systematic-debugging` before any edit |

## When the context fills up

- Past roughly 40 percent, stop adding L3 detail. Write the state to the ledger
  (`.superpowers/sdd/<plan>/progress.md`), then continue in a fresh context with L1 and L2
  only. The ledger is the recovery map; trust it over recollection.
- A long investigation that only needs its conclusion belongs in a subagent or a Codex
  worker, whose context is not this one.
- Never summarise a contract from memory when the file is one read away. A rule recalled
  approximately is a rule broken exactly.
