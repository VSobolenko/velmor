## Context

See `proposal.md` - Why. What shapes the approach is the state of the parts and
the interfaces between them:

- `ScoutJob.run(query, run_id)` already discovers, partitions per-source failures
  and persists candidates, returning `ScoutRun`. It is plain Python and has no
  tests.
- The auditor is a LangGraph graph: `collect_declared_evidence -> resolve_license`
  with a conditional edge to `decide`, `investigate` (loop) or `review`
  (interrupt), and `decide` as the terminus. Every node exists and none is tested.
- `AuditorRunner.run_once()` selects undecided candidates, invokes the graph per
  candidate in its own thread, saves a `GateDecision` and returns the decisions.
- `ProhibitedCategoryScreen.screen(candidate) -> ScreeningResult` exists, is
  tested, is constructed in `Container`, and is called from nowhere.
- Evidence kinds in play: `SOURCE_API_FIELD` (tier A declared licence),
  `LICENSE_FILE` (text quoted from the item's own fetched page), `SPDX_MATCH`
  (identity resolved by the matrix), `LLM_EXTRACTION` (the model's claim),
  `HUMAN_ATTESTATION` (a review ruling).

## Goals / Non-Goals

**Goals:**

- One path a test can walk with no network, no model and no database: candidate in,
  publish-or-refuse out.
- Screening consulted in the path, with its refusals counted and explained.
- One aggregate per pass, stating an outcome for every candidate it touched.
- Node-level tests for every node, and a routing test covering every branch
  including the attempt cap and the give-up path.

**Non-Goals:**

- Delivering a human ruling into a resumed run.
- Persisting a pass report, or exposing it over the API.
- Changing the policy table, the resolver, the gate's conditions or
  `SourceConnector`.

## Decisions

### Screening is a stage before the graph, not a node inside it

The screen runs in the runner, over each selected candidate, before the graph is
invoked. A candidate that matches is reported as screened out and never enters the
graph.

Alternatives considered. A node inside `AuditorState`: rejected, because a
`GateDecision` carries a `RightsRecord`, so representing "refused without asking a
licence question" inside the graph would require either a fabricated verdict or a
second decision type threaded through state - and a fabricated verdict is exactly
the unexplained ruling this project exists to prevent. Screening inside the gate:
rejected, because the gate can only see a `RightsRecord`, so the licence question
would have to be answered before the category question, inverting the order the
specs define.

Layer: the screen stays in `packages/services/src/screening` (deterministic, no
agent dependency); the caller is `packages/auditor`, which may import services.

### A hesitant reading escalates; a settled one does not

The router reads `confidence` from the interpretation, so an identity that
resolved from a model reading the page is acted on only when the model is sure of
what it read. Without that, a resolved identity plus the quoted sentence is enough
evidence for the gate to publish - a page quote is source evidence - so a hesitant
guess would become a listing. A licence the source declared needs no reading, and a
human ruling settles the identity, so neither escalates. `AUDITOR_ESCALATION_CONFIDENCE`
was documented as this threshold but read nowhere before this change; the router is
where it belongs, because the decision is a function of accumulated state.

### The pass report is a new domain model with four outcomes

`VerificationRun` in `packages/services/src/domain/` carries one
`VerificationOutcome` per candidate: published, refused, screened out, or paused
for review, each with its reasons, plus the screened-out counts per category.

Rationale: the four outcomes are not interchangeable and cannot be collapsed into
one type without lying. A screened-out candidate has no record; a paused candidate
has no decision; only published and refused have a `GateDecision`. Forcing them
into `GateDecision` would assert a verdict that was never reached.

Alternative considered: extend `ScoutRun`. Rejected - discovery and verification
report different facts, and a shared model would grow a union of both.

### Aggregation happens in the runner, not in graph state

The graph produces a per-candidate state; the pass report is a fact about the run.
Adding a report channel to `AuditorState` would make every node responsible for
bookkeeping and would break node idempotence under a checkpoint resume, where a
restarted node must not double-count. The runner already performs the post-graph
effect (saving the decision), so it is the natural owner.

### The verification pass stays LangGraph; screening stays plain Python

LangGraph is justified for the verification pass because its control flow branches
on resolved state, loops on investigation attempts against a bound, and interrupts
for a human. None of that is expressible as a straight line of calls without
reimplementing a scheduler. Screening is a keyword test over the candidate: a
decision decidable from the input, so per
`.cursor/rules/05-agent-graphs.mdc` it must not become an agent. No Pydantic AI
beyond the existing interpreter, and DeepAgents is not involved.

### Testing shape

Every node gets a test with a hand-built `AuditorState`, because a node tested only
through a full run is tested for the graph's routing, not for the node. Routing
gets a table-driven test with a case per branch: resolved, attempts remaining,
attempts exhausted. One path test walks discovery to ruling with a fake connector,
a fake page fetch, a fake interpreter and the in-memory store, so the graph builds
and runs with no network, no model and no database.

## Risks / Trade-offs

- **[A paused candidate is re-selected every pass and re-investigated]** →
  `pending_audit` selects candidates with no record, and a paused candidate has
  none, so the next pass repeats the investigation and the interrupt, costing a
  fetch and a model call each time. Mitigation: the pass report states the paused
  count, so the cost is visible rather than silent. Excluding paused candidates
  requires delivering the human ruling, which is a non-goal of this change; it is
  named here so it is not discovered as a surprise.
- **[`LICENSE_FILE` is trusted as source evidence although a model chose the
  quoted sentence]** → on the path where the source declares no licence, the
  evidence is a page quote plus the model's claim, and the page quote satisfies the
  gate's source-evidence check. So a model reading can still lead to publication,
  which is the class of problem the 1.1.0 tightening addressed one route of.
  Mitigation: pending a decision, this change neither widens nor narrows the gate
  and its specs assert only the behaviour that exists. Closing the route properly
  means attributing evidence to the fetched artifact (store the document or its
  digest and the excerpt's position) so `LICENSE_FILE` rests on an observation
  rather than on a model's selection. Not done here: it changes what may be
  published and needs its own decision and its own change.
- **[Screening refuses items the rights engine would have approved]** → that is
  the intent, but it removes catalogue. Mitigation: refusals are counted per
  category per run, and the archive note must state the effect. Screening can only
  remove; it can never make something publishable.
- **[The screen matches terms, not meaning]** → a candidate whose prohibited nature
  is expressed only in a language the list does not cover is not caught by it, and
  the spec says so rather than claiming a guarantee the code does not provide. The
  control for that case is the source allowlist: Velmor crawls sources that do not
  carry these goods, and the screen is the backstop for a mislabelled item that
  slips through. A semantic screen would need a model in the path, which is not
  what this change is for.
- **[The path test uses fakes, so the live Openverse path is unproven]** → the
  path test proves wiring and logic, not that Openverse is reachable or that the
  payload still matches. Mitigation: one manual live pass is the acceptance
  evidence, and it is stated as a manual step rather than reported as a passing
  check.
- **[The graph has one terminus for both "decided" and "gave up"]** → an
  unresolved candidate that exhausts its attempts reaches `decide` through
  `review`, the same node as the success path. Accepted: what distinguishes the
  outcomes is the verdict the deterministic engine reaches on the accumulated
  evidence, and `decide` cannot publish an unresolved licence. A separate node
  would duplicate the decision logic to produce a differently-named refusal.

## Migration Plan

No schema change and no data migration: the report is not persisted and the
candidate and record models are untouched. Deployment is a normal code deploy.
Rollback is a revert of the change; nothing written by it needs undoing, because
the only persisted effect is a `GateDecision` that the previous code would also
have been able to produce.

## Open Questions

Whether a pass report should be persisted and exposed, so that a runtime check
could assert over a run's outcomes rather than reconstructing them. Deferrable
without changing these specs, the approach or the task breakdown; it becomes its
own change if wanted.
