---
name: agent-graph
description: How the agents are structured and how to add or change a LangGraph node, edge, state field or interrupt in the auditor graph, plus when the task should NOT be a graph. Load when editing packages/auditor, packages/scout, or velmor/agents.
---

# agent-graph

Read `.cursor/rules/05-agent-graphs.mdc` as well; that rule is canonical. This
skill is the map of the code.

## Pick the tool before writing anything

| Tool | Use it when | Do not use it when |
|------|-------------|--------------------|
| Plain Python | The answer is decidable from inputs: policy, verdicts, gating, screening, discovery | Any judgement is needed |
| LangGraph | Control flow is a graph: branching, cycles, retries, human-in-the-loop, resumable state | A straight line of calls would do |
| Pydantic AI | One structured extraction from text into a typed model | You need multi-step orchestration |
| DeepAgents | Open-ended long-horizon research where the path is unknown | The steps are known in advance |

Start at the top and move down only when the layer above provably cannot express
the requirement.

This is already reflected in the repository, and the shape is the decision:

- **Scout is plain Python.** `packages/scout/src/ingest.py` plus `runner.py`. A
  discovery pass is a loop over queries and connectors; a graph would add state,
  checkpointing and a framework for no branching. Do not "upgrade" it to LangGraph.
- **Auditor is a LangGraph graph.** It branches on whether the declared license
  resolves, loops on investigation attempts, and interrupts for human review. That
  is control flow, so it is a graph.
- **The rights verdict is never an agent.** No model, graph or framework may sit
  between evidence and `RightsVerdict`.

## The auditor graph

| File | What it owns |
|------|--------------|
| `packages/auditor/src/state.py` | `AuditorState` (`TypedDict`) |
| `packages/auditor/src/node_names.py` | node-name constants: `COLLECT_DECLARED_EVIDENCE`, `RESOLVE_LICENSE`, `INVESTIGATE`, `REVIEW`, `DECIDE` |
| `packages/auditor/src/nodes/` | one module per node |
| `packages/auditor/src/nodes/routing.py` | the conditional routers |
| `packages/auditor/src/graph.py` | graph assembly |
| `packages/auditor/src/runner.py` | drives the graph, screens candidates first, and performs the effects afterwards |
| `velmor/agents/auditor.py` | the CLI-facing agent that builds the container, calls the runner and prints the pass report |

`AuditorState` carries `candidate`, `source`, `evidence`, `resolved_license_id`,
`interpretation`, `investigation_attempts`, `human_ruling`, `record`, `decision`.

## Rules that are easy to get wrong

- **State is a `TypedDict`** in `state.py`. A node returns only the keys it
  changes, not the whole state.
- **`evidence` is a plain list, not a reducer channel**, on purpose: each node
  returns the full list it computed from the list it received. LangGraph restarts an
  interrupted node from the top on resume, so a node that appends to a shared list
  would double-count. Do not "simplify" this into an `operator.add` reducer.
- **Nodes are idempotent.** A resumed run may re-execute any node from a
  checkpoint.
- **A node never performs an effect the run must not repeat.** No push, no publish,
  no purchase inside a node. The graph produces state; `runner.py` performs the
  effect after the graph completes.
- **A node does not catch exceptions to keep the run alive.** An upstream failure
  is either a recorded failure carried in the state or an exception that fails the
  run. `try/except` is forbidden by `.cursor/rules/03-error-handling.mdc` unless
  authorized and proven.
- **Routing uses the constants in `node_names.py`,** never string literals
  scattered through edge definitions. A typo'd node name is a silent unreachable
  branch.
- **Conditional routing is a function of state only.** No I/O in a router.
- **Every cycle needs a hard bound.** The investigate loop reads
  `investigation_attempts` against `AUDITOR_MAX_INVESTIGATION_ATTEMPTS`, so a
  non-converging run terminates instead of burning the budget.
- **Interrupts use `interrupt()` and require a checkpointer.** `REVIEW` is the
  human-in-the-loop node, gated by `AUDITOR_ESCALATION_CONFIDENCE`. The
  checkpointer is opened on demand by `Container.checkpointer()`; only the auditor
  uses it, because discovery has no state worth keeping across a restart. A graph
  that interrupts without a checkpointer cannot be resumed and the run is lost.
- **An uncertain reading escalates without interrupting the run.** A resolved
  identity that came from a model reading the page is only acted on when
  `interpretation.confidence` reaches `escalation_confidence`; below it the router
  goes to `DECIDE`, which records no ruling, so the run pauses and the candidate is
  reported as paused. The threshold is read by the router, not by a node, because
  the answer is a function of accumulated state.

## The runner's contract

`AuditorRunner.run_once()` takes the next batch of candidates and returns one
`VerificationRun` describing what happened to each of them.

- **Screening happens before the graph.** `ProhibitedCategoryScreen` runs over the
  batch first, so a prohibited candidate never reaches the rights engine and no
  model is called about it. Screening can only remove.
- **Four outcomes, not two.** `PUBLISHED` and `REFUSED` carry a `GateDecision` and
  its reasons; `SCREENED_OUT` and `PAUSED` carry reasons and no decision, because
  no ruling was made. Reporting either of those as a refusal would assert a
  decision nobody made.
- **The report is exhaustive.** Every candidate the pass selected appears once, in
  selection order, and refusals are counted per prohibited category. A pass that
  lists only what it published hides its own losses.
- **A candidate from an unregistered source fails the run.** `registry.by_id` raises
  `UnknownSourceError` rather than skipping the candidate, because a candidate whose
  source is gone means the registry and the database disagree, and a pass that
  quietly ignored it would look clean.

## Adding a node

1. Add the name constant to `node_names.py`.
2. Add the state field(s) it writes to `AuditorState` in `state.py`.
3. Create `packages/auditor/src/nodes/<name>.py` with a node class whose method
   signature is `state -> partial state`.
4. Wire it in `graph.py` and, if it is conditional, add the branch in `routing.py`.
5. Ensure it is idempotent, and that it performs no repeatable effect.
6. Test the node directly with a hand-built state - never only through a full graph
   run - plus a routing case for every branch, including the retry cap and the
   give-up path.
7. Building the graph must not require a network, a database or an API key. Push
   provider construction into the node classes and inject the container.

## The LLM boundary

`packages/services/src/llm/license_interpreter.py` performs the one structured
extraction: a `LicenseInterpretation` from fetched text, via Pydantic AI. Its
output is evidence, never a verdict. A model-proposed license identity becomes an
`Evidence` record of kind `LLM_EXTRACTION`, and the gate treats that as
inferential, so it can never be the only thing supporting a publication.
