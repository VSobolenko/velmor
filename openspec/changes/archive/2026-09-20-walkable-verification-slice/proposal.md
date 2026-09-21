## Why

The rights engine, the publication gate and both agent scaffolds exist and are
individually tested, but nothing proves they work together. No test drives a
candidate from a source through verification to a publish-or-refuse ruling; the
prohibited-category screen is wired into the container and consulted nowhere in
the path; and a verification pass reports per-decision lines but no aggregated
outcome. What exists is a set of correct parts, and a platform whose claim is
"nothing is published that cannot be justified" cannot rest on parts. This change
makes one path walkable end to end and proves it.

## What Changes

- **Screen prohibited candidates before the rights path.** A candidate that
  matches a prohibited category is refused with a reason and produces no
  `RightsRecord`. Screening refuses; it never rewords, and a refusal is counted
  and reported rather than dropped.
- **Add a verification-run report.** One pass returns an aggregate: how many
  candidates were screened out, how many were decided, how many were paused for
  human review, and the per-candidate outcome with its reason. Today the only
  aggregate is a print statement.
- **Build the verification graph through the composition root** so a pass is
  runnable against a real source end to end, and so a test can build the same
  graph with fakes and no network, no model and no database.
- **Prove the flow with tests.** Discovery, screening, resolution, the bounded
  investigation loop, the review interrupt and the gate each get a node-level
  test with a hand-built state, plus one integration-style test running the whole
  path over a fake connector. The live Openverse run stays a manual step.
- **Record discovery's contract as a spec.** `ScoutJob` already behaves correctly
  and has never been specified; the slice's guarantee starts there, so the
  contract is written down and asserted.

Explicitly unchanged: the policy table, the resolver, the gate conditions and
`SourceConnector`. Screening refuses before a record is produced, so no existing
verdict changes and `ENGINE_VERSION` is not bumped.

## Capabilities

### New Capabilities

- `discovery/candidate-ingest`: one discovery pass over the enabled sources -
  which sources were queried, candidates normalised and stored, per-source
  failures reported, and no silent shrinking of the funnel when an upstream
  breaks.
- `verification/prohibited-screening`: a prohibited category is refused before
  any rights work happens, with a human-readable reason, counted in the pass
  report, and never neutralised by renaming, translating or bundling.
- `verification/rights-decision`: one verification pass turns each candidate
  without a verdict into a publish-or-refuse ruling, or pauses it for a human
  ruling under a hard attempt bound, records the outcome append-only, and reports
  the aggregate.

### Modified Capabilities

None. `openspec/specs/` does not exist yet, so every capability here is
established by this change rather than modified.

## Non-goals

- Publishing to Saleor, taking payment through Stripe, and the HTTP API. Those
  are separate changes; this one stops at the ruling.
- Resuming a paused verification run from a human ruling. The graph already
  interrupts; delivering the ruling into a resumed run is its own change.
- Persisting pass reports. A report is returned to the caller, not stored.
- New sources and new connectors. Openverse is the only enabled source and stays
  the only one.
- Any change to the rights policy surface. If a task in this change appears to
  need the rights rules relaxed to pass, the task is wrong.

## Impact

- **Code**: `packages/scout` (ingest and runner tests), `packages/auditor` (a
  screening stage, routing, the pass report, node and routing tests),
  `packages/services` (the report and screen-out models; the screening package
  gains its caller), `velmor/agents` (wiring and reporting), `velmor/container.py`
  (the screen and the graph become reachable from one composition point).
- **Dependencies**: none added.
- **Contracts**: no GraphQL, HTTP or storefront contract changes. The
  `GateDecision` shape is unchanged; a screened-out candidate is represented
  outside it on purpose, because a `GateDecision` implies a verdict was reached.
- **Catalogue effect**: some candidates that previously reached the rights path
  are now refused before it. The number is reported per run, and the archive note
  must state it. No good that was publishable on a full record becomes
  unpublishable through this change.
