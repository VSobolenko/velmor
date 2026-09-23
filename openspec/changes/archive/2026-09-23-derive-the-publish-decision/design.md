## Context

The publication path builds its own `GateDecision` instead of asking the gate, and the guard that
`.cursor/rules/06-rights-engine.mdc` and `rights-verify.md` invariant 5 both name does not exist in
the code. This design is about where the derivation belongs, what the guard must actually guard,
what a ruling from a superseded engine should do, and why the rule text is part of the change
rather than a follow-up.

Measured inputs, all on the deployed tree:

| Fact | Observed |
|---|---|
| `raise RightsDeniedError` in the repository | none |
| Production callers of `PublicationGate.decide` | one, `packages/auditor/src/nodes/decide.py:44` |
| `engine_version` of the 105 publishable records | `1.1.0`, all of them |
| Running engine | `1.2.0` |
| Current gate re-run over the 105 stored records | 105 publishable, 0 refused |
| Evidence kinds on those records | `source_api_field` + `spdx_match`, all 105 |
| Records carrying `LLM_EXTRACTION` or `HUMAN_ATTESTATION` | none |
| Candidates `pending_audit` can select | only those with no record at all |

## Layer placement

| Piece | Layer | Why |
|---|---|---|
| The derived decision | `velmor/publish.py` | The composition root already builds the gate and already fetches `spec`. It is the only place that knows which records are being published. |
| The guard | `packages/services/src/commerce/publication.py` | The bridge is the last point before an entry exists. A guard that runs earlier can be bypassed by the next caller; a guard here cannot. |
| `RightsDeniedError`'s docstring | `packages/core/src/errors.py` | Where the error already lives. One sentence, no behaviour. |
| The rule and the invariant | `.cursor/rules/06-rights-engine.mdc`, `.cursor/commands/rights-verify.md` | The rule is the claim; it must state what the code does. |
| The sensor | `scripts/selftest.mjs` | The rule now says the guard fires, so something must fail when it does not. |

No rights, screening, connector, gate-condition or policy file changes. `PublicationGate.decide` is
called more often, not altered. Plain Python, because every step is decidable from its inputs: no
branching to model, nothing to persist, no extraction, no research. LangGraph, Pydantic AI and
DeepAgents are all the wrong tool for the reasons in `.cursor/rules/05-agent-graphs.mdc`.

## D1 - The caller derives, and the bridge re-derives

`velmor/publish.py` replaces the hand-built `GateDecision` with `gate.decide(spec, record)`. That
alone fixes the attribution: the decision object is then the gate's output, and the record it
carries is the one the gate judged.

It is not enough on its own. A rule that says "publishing without a passing verdict raises
`RightsDeniedError`" is a statement about the *caller*, and a caller that derives correctly is
never the one that violates it. The next caller - a new command, a script, an operator path - would
be trusted on its assertion again. So the bridge re-derives as well:

- `PublicationBridge.apply` computes the gate's ruling from `spec` and `decision.record`, not from
  `decision.publishable`.
- When the caller's decision claims `publishable=True` and the gate's own ruling disagrees, it
  raises `RightsDeniedError`.
- When the caller's decision claims `publishable=False`, the existing `_when_not_publishable`
  branch runs, which it could not before.

Rejected: trusting `decision.publishable` with a comment asking callers to derive. That is the
arrangement that produced this defect. Rejected: deriving only in the bridge and leaving the caller
alone. Then the decision object the caller builds is still a lie, and the report still prints the
outcome of an assertion. Rejected: a new port for "is this publishable". The gate is that port.

## D2 - The guard raises; it does not repair and it does not warn

`RightsDeniedError` is raised, not logged, and the bridge does not attempt to withdraw on the
caller's behalf when the caller asserted publishable. The two cases are different:

- A decision that is **not publishable** is a normal, contract-carrying outcome: the bridge
  withdraws an existing entry or reports the refusal, with the gate's reasons. That is
  `_when_not_publishable`, and it stays a value.
- A decision that **asserts publishable while the gate refuses** is not an outcome at all. It means
  the caller did not use the gate. There is no honest entry to write and no reason to report
  against; the run must stop and say so. The rule already forbids catching it into a warning.

This is the one place in this change where an exception is the right shape, and it needs no
authorization under `.cursor/rules/03-error-handling.mdc` because it is a raise, not a catch: the
change adds no `try` and no `except`.

## D3 - A superseded engine version is reported, never refused

The tempting rule is "refuse a record whose engine is not the running one". Measured, it disables
the shop: all 105 records are `1.1.0` and the engine is `1.2.0`, so a refusal withdraws every good
and the storefront empties. That is not caution, it is an outage, and it would be caused by a check
that had never been run against live data.

So the mismatch is reported:

- the reason is attached to the outcome, so it appears in the operator's report beside the action;
- it does not change the action, so today's behaviour is identical;
- it is not a warning written into a log that nobody reads, because `velmor publish` prints outcomes
  with their reasons and that is already where an operator looks.

Why report at all, when the measured divergence is harmless: because the harm is prospective. The
first good decided with a model reading or a human ruling is decided under a claim priority the
published catalogue has never been judged by, and by the time it matters the ruling is already
published. A line in the report is the smallest thing that can be acted on.

Rejected: bumping `ENGINE_VERSION` as part of this change. No verdict path is edited, so nothing
would justify it, and it would make all 105 records stale by definition.

## D4 - The re-decision gap is named, not built

`PostgresStore.pending_audit` selects candidates where `rights_records.candidate_id IS NULL`. A good
that already has a record is never reconsidered, so a superseded ruling is permanent. This is the
real hole behind D3, and this change deliberately does not close it.

Why not: closing it means an operator-driven re-audit with a defined effect on live entries - what
happens to a published good whose new verdict is DENIED, what happens to an entitlement already
granted, whether a re-decision is a new record or a superseding one under the append-only rule.
Those are product decisions with a legal surface, and taking them inside a change about attribution
would be exactly the "smallest change" rule broken.

What this change owes instead is the visibility that makes the next one possible: after it, a
publication that carries a superseded ruling says so, and the count is measurable. Recorded as the
first item of the follow-up work, not as a silent omission.

## D5 - The rule text and the sensor move with the code

The rule and the invariant are not documentation of this code; they are claims an agent reads and
acts on, and both currently describe a guard that does not exist. Leaving them while fixing the code
would leave two false statements in the repository, which is the defect this project's harness rules
exist to prevent.

So the change does three things together, and none of them alone:

1. the code derives and raises;
2. the rule and invariant 5 say what it does;
3. `scripts/selftest.mjs` asserts the guard fires on the path that must raise it, so the claim is
   tested rather than restated.

Following `.cursor/rules/08-evidence-and-sensors.mdc`: the check is proved by injecting the defect -
restoring the hand-built decision - and watching it fail, then removing the injection and watching
it pass, with both runs recorded.

## What the buyer sees, page by page

No page changes, and this is a consequence of the design rather than an omission: the change edits
no presentation code, adds no string, and the catalogue it acts on measures 105 publishable and 0
refused before and after. No locale dictionary, component, layout rule or asset is touched, so the
buyer-surface checklist has nothing to add. The verification for this change is therefore the
publication path's own evidence - the report, the counts, and the injected-defect runs - and
`/ux-verify` is not owed, because nothing a buyer reads or acts on can differ. If the implementation
turns out to need a buyer-visible change, that is a signal the design was wrong and the work stops.

## Failure modes

| Failure mode | Handling |
|---|---|
| A caller asserts publishable for a record the gate refuses | `RightsDeniedError`, run stops, no entry written |
| A caller passes a non-publishable decision | `_when_not_publishable`, unchanged: withdraw or report, with reasons |
| A record's engine version is not the running one | Reported as a reason on the outcome; the action is unchanged |
| The bridge's re-derivation disagrees with the caller's for a legitimate reason | Not possible: both call the same gate with the same `spec` and the same record, and the gate is a pure function of its inputs |
| A good already published is stale | Nothing changes it; the gap is D4, named and measured |

## New dependencies

None. No new setting, no new model, no new port and no schema change: `PublicationAction` keeps its
values, so the report's shape is stable and no stored data is touched.

## Deliberately not done

- **Re-deciding a good under a new engine** (D4). What would have to be true: the product decisions
  above have answers, and the append-only rule has an agreed meaning for a superseding record.
- **Refusing on a stale engine version** (D3). What would have to be true: no good on sale carries a
  superseded ruling, which requires D4 first.
- **Removing `RightsDeniedError` and correcting only the rule text.** Cheaper, and it would leave the
  gate bypassable by the next caller. Considered and rejected because the code, not the prose, is
  what enforces.
- **Making `pending_audit` select decided candidates.** That re-decides goods as a side effect of a
  routine pass, with no decision about what happens to a published entry whose verdict flips. Wrong
  place, and it is D4.
- **Any change to the gate's conditions.** No evidence kind, tier, grant or licence moves.
