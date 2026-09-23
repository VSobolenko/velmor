## Why

`/rights-verify` invariant 5 states that publishing without a passing verdict raises
`RightsDeniedError`, and `.cursor/rules/06-rights-engine.mdc` states the same as a rule. Neither
is true of the code. Measured on the deployed tree at `/opt/velmor/app`:

- `grep -rn "raise RightsDeniedError"` across the whole repository: **no raise site**. The symbol
  is defined in `packages/core/src/errors.py` and exported; nothing raises it.
- `PublicationGate.decide` is called in exactly one production place, the auditor's decide node
  (`packages/auditor/src/nodes/decide.py:44`). The publication path never calls it.
- `velmor/publish.py` reads `(candidate, record)` pairs from `PostgresStore.published` and builds
  the decision by hand:

  ```python
  decision = GateDecision(
      candidate_id=candidate.id,
      publishable=True,
      reasons=(),
      record=record,
  )
  ```

  The `spec` that `gate.decide(spec, record)` needs is fetched one line later, so both arguments
  were already in hand.

The consequence is not that a good reaches the shop without a verdict. Nothing does:
`PostgresStore.published` selects `rights_records.publishable IS TRUE`, a column only the gate
writes, and the store's own docstring says so. The consequence is narrower and worse to live with:

- **The decision is an assertion, not a derivation.** `PublicationBridge` has a
  `_when_not_publishable` branch, built to withdraw an entry when a decision is not publishable.
  On the publication path that branch is unreachable, because the only caller passes
  `publishable=True` unconditionally. The guard branch exists and cannot fire.
- **A divergence between the column and the record it came from would be invisible.** Measured on
  the live catalogue: 0 of 105 publishable records diverge, so this is latent rather than realised.
- **A ruling of a superseded engine is carried silently.** Every `RightsRecord` stamps
  `engine_version`, and the docstring of `RightsResolver.ENGINE_VERSION` says it is stamped "so a
  publication ruling is always attributable to the policy that produced it". Nothing reads it back:
  neither `published()` nor the hand-built decision compares it with the running engine. Measured:
  **all 105 publishable records were produced by engine `1.1.0`, and the deployed engine is
  `1.2.0`**, whose own docstring says it changes the verdict by making the decision follow the
  licence claim the run established.
- **A good cannot be re-decided under a new engine.** `PostgresStore.pending_audit` selects
  candidates where `rights_records.candidate_id IS NULL` - only candidates that have never been
  decided. Combined with append-only records, no candidate that already has a record is ever
  reconsidered. A verdict-changing bump is therefore permanent for every good already decided, and
  nothing in the product can notice or repair it.

### What is measured, and what is not

The exposure from the `1.1.0 -> 1.2.0` bump was reconstructed over the stored inputs using the real
resolver and the real gate:

- Rerunning the current gate over all 105 stored records: **105 publishable, 0 refused**. Every good
  on sale stands on `source_api_field` plus `spdx_match`, and every one is a tier A source, so the
  legal basis of the catalogue is intact today.
- **No publishable record carries `LLM_EXTRACTION` or `HUMAN_ATTESTATION`.** The reordering `1.2.0`
  introduced - a human ruling or an investigated page winning over the source's declared field - has
  no instance to act on, so for these 105 goods `1.1.0` and `1.2.0` select the same claim by
  construction.
- So the re-audit produced no change, and could not have. That is the point: the exposure is
  prospective. It appears the first time a good is decided with a model reading or a human ruling,
  and by then the ruling that should have been superseded is already published and unpublishable
  proof of it does not exist.

### What the buyer will see

Nothing. This change reads and re-derives decisions; it adds no page, no component, no string, no
layout and no locale, and it changes no `PublicationAction` a buyer could observe. On the measured
catalogue its behaviour is identical, because the gate already accepts all 105 records. What
changes is that the publication decision can no longer be an assertion, and a ruling from a
superseded engine can no longer pass in silence.

### The licence concern, stated explicitly

- **Which licence action.** Unchanged: selling a download is `RightsAction.RESELL`, decided by the
  existing `PublicationGate`.
- **Which evidence.** Unchanged. No evidence kind is added, removed or reordered, the policy table
  is not touched, and no gate condition changes.
- **What the platform refuses when the evidence is missing.** Unchanged. This change does not widen
  or narrow what the gate accepts; it removes the ability to publish a decision the gate did not
  produce.

### Effect on existing verdicts

None, and this is asserted rather than assumed: the current gate was run over every stored record
and returned the same ruling for all 105. `RightsResolver.ENGINE_VERSION` does not move; a bump is
owed only when a verdict could change for identical inputs, and no verdict path is edited here.

## What Changes

- **The publication path derives its decision.** `velmor/publish.py` calls
  `PublicationGate.decide(spec, record)` instead of constructing `GateDecision(publishable=True)`.
  The gate becomes the author of every decision that reaches publication, as the architecture
  document already says it is.
- **The guard the rule names becomes real.** `PublicationBridge.apply` re-derives the gate's ruling
  from the decision's own record and raises `RightsDeniedError` when a caller asserts
  `publishable=True` for a record the gate refuses. That is what the rule describes. It also makes
  the `_when_not_publishable` branch reachable, so a non-publishable decision has a defined effect
  instead of being unreachable code.
- **A ruling from a superseded engine is reported.** Publication compares the record's
  `engine_version` with the running engine and reports the mismatch as a reason on the outcome, so
  it appears in the operator's report. It does not refuse: all 105 records are `1.1.0` against a
  `1.2.0` engine, so refusing would withdraw the entire catalogue for a divergence this change has
  measured to be harmless. A refusal belongs with the capability to re-decide, which this change
  does not build.
- **The rule and the invariant are corrected together with the code.** Invariant 5 and
  `.cursor/rules/06-rights-engine.mdc` currently state a guard that does not exist. After this
  change they state what the code does, and `scripts/selftest.mjs` gains a check that the guard is
  actually raised on the path that must raise it, so the claim cannot drift from the code again.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `commerce/catalog-publication`: the publication decision is derived from the gate, a caller
  asserting a ruling the gate did not produce is refused with `RightsDeniedError`, and a ruling
  recorded under an engine other than the running one is reported rather than carried silently.

Written as an ADDED requirement rather than as a modification, because `redesign-storefront-ux`
holds an unmerged delta on this same capability and two changes editing one requirement in parallel
is how a contract gets corrupted. Folding it in is a follow-up once those merges land.

## Non-goals

- **No capability to re-decide a good under a new engine.** The gap is real and is stated in
  `design.md` as the thing this change deliberately leaves: `pending_audit` cannot select a decided
  candidate, so a superseded ruling is permanent. Building it means an operator-driven re-audit with
  a defined effect on live entries, which is its own change. This change makes the state visible so
  the next one has something to act on.
- **No refusal on a stale engine version.** Measured: it would withdraw all 105 goods.
- **No engine version bump.** No verdict path is edited.
- **No policy change.** No licence, grant, tier or gate condition moves.
- **No storefront, API or buyer-surface change.**
- **No new dependency.**
- **No change to what the auditor writes.** Records stay append-only and the auditor keeps its
  single call site for `decide`.

## Impact

**Code**

- `velmor/publish.py` - derive the decision from the gate, and report a stale engine version.
- `packages/services/src/commerce/publication.py` - re-derive and raise `RightsDeniedError` on a
  caller's assertion the gate contradicts.
- `packages/core/src/errors.py` - `RightsDeniedError`'s docstring states the case it now covers.

**Docs and harness**

- `.cursor/rules/06-rights-engine.mdc` - the guard sentence states what the code does.
- `.cursor/commands/rights-verify.md` - invariant 5 states what is now enforced and how it is
  observed.
- `scripts/selftest.mjs` - a check that the guard is raised on the path that must raise it.

**Tests**

- `velmor/tests/unit/test_publish_command.py`, and the bridge's cases in
  `packages/services/tests/unit/commerce/test_publication.py`, including the case where a caller
  asserts publishable for a record the gate refuses.

**Risk**

The main risk is the guard being too eager: if the bridge re-derives and the gate's ruling depends
on anything the bridge does not hold, a publishable good would be refused. It holds `spec` for
exactly that reason, and the measured catalogue is 105 publishable and 0 refused, so the change is
observably behaviour-preserving on live data. The second risk is that reporting a stale engine
version is treated as noise; it is a reason on the outcome and a line in the report, which is the
smallest signal that can be acted on and the most that is honest without a re-decision path.
