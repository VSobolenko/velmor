---
name: "/rights-verify"
id: "rights-verify"
category: "Review"
description: "Domain runtime verifier — change-impact sweep proving the publication gate still refuses what it must"
---

# /rights-verify — domain runtime verifier

Catches what static review cannot. `bugbot` and `security-review` read diffs.
`ruff` and `compileall` prove the code is well-formed. `pytest` proves the tests
that exist still pass — and that is the gap: a gate that has quietly stopped
refusing something still passes every test that was written before the change,
because nobody wrote a test for the thing that broke.

This role is the "second agent that checks the door". It does not fix code. It
finds defects in the publication decision and hands them to the `/ship` fix loop.

## The invariants this command exists to prove

These are the assertions. Every run checks all of them, against the changed
surface, with real inputs.

1. **Deny by default.** A licence string that resolves to nothing is not
   publishable. An empty or unknown `license_id` is `UNKNOWN`, never a pass.
2. **No source evidence, no publication.** Evidence that is absent, or that
   consists only of a model reading plus an identity match derived from it, is not
   publishable, and the refusal names what is missing. Assert this with a record
   whose evidence is `(LLM_EXTRACTION, SPDX_MATCH)` in that order: it must be
   refused. That combination is the one that previously published, so it is the
   case worth re-checking after any change to the gate.
3. **A denied action blocks publication.** If the licence does not grant the
   action the listing requires, the decision is not `PUBLISHABLE`.
4. **Every refusal has a reason.** A non-`PUBLISHABLE` `GateDecision` with an empty
   reason list is a bug.
5. **The gate has no bypass.** `PublicationBridge.apply` re-derives the gate's ruling
   from the decision's own record and raises `RightsDeniedError` when a caller presents a
   decision claiming the record is publishable while the gate refuses. No entry is created
   for it and an entry already present is left untouched. Observe this by running the case
   that asserts the raise - `TestCallerAssertionTheGateContradicts` in
   `packages/services/tests/unit/commerce/test_publication.py` - never by reading the code.
   A decision that states the record is *not* publishable is an outcome, not an error: the
   bridge withdraws or reports, carrying the gate's reasons. There is no second path and no
   "already approved" shortcut.
6. **Determinism.** The same `(candidate, grant, evidence)` produces an identical
   verdict twice in a row, and the verdict path touches no clock, network, model or
   filesystem. Verify by freezing and re-running, not by reading the code.
7. **Layer purity.** `packages/services/src/rights/**` imports no LangGraph, no LLM
   provider, no connector, no agent package.
8. **A source failure is visible.** A connector that errors mid-run produces a
   `SourceFailure` in the run result. It does not silently shrink the funnel to an
   empty page.

## Core principle: change-impact scope, never a fixed list

A fixed smoke list misses the regression next door. Derive the surface from the
diff and err toward over-covering.

### 1. Read the diff

`git diff --name-only` for uncommitted work, or `git diff <base>...HEAD --name-only`
for a branch.

### 2. Classify blast radius

| Changed path | Minimum sweep |
|---|---|
| `packages/services/src/rights/**` | `packages/services/tests/unit/rights` + all eight invariants |
| `packages/services/src/domain/**` | `packages/services/tests/unit` (every consumer of the model) + invariants 1-4 |
| `packages/services/src/screening/**` | `packages/services/tests/unit/screening` + invariant 5 |
| `packages/services/src/sources/**` | `packages/services/tests/unit/sources` + credential validation on an enabled source + invariant 8 |
| `packages/services/src/connectors/**` | the touched connector's contract tests + invariant 8 |
| `packages/services/src/persistence/**` | the store contract tests against both implementations + invariant 6 |
| `packages/services/src/llm/**` | interpreter tests; if a prompt changed, an eval run, and confirm the interpreter still cannot produce a verdict |
| `packages/auditor/**` | auditor node tests + the routing table test + confirm no node performs a publish |
| `packages/scout/**` | scout tests + the ingest job + invariant 8 |
| `packages/core/**` | `packages/core/tests/unit` including the architecture layering test |
| `velmor/**` | import and construct smoke: `uv run python -c "from velmor.container import Container"` and `uv run python -m velmor --help` |
| `openspec/**` | `openspec validate --strict "<change-name>"` |

When unsure whether something is affected, include it. A false "all good" here is
worse than a slower check.

### 3. Write the checklist down

One item per module or invariant, with the concrete assertion. The checklist is the
record of what was and was not covered; state the uncovered items explicitly in the
report rather than leaving them implied.

## Steps

### 0. Determine the target

- Rights or screening changed → the full invariant set is mandatory.
- An agent package changed → invariant 5 (no publish from a node) and the routing
  tests.
- Only docs or harness changed → say so and run only the spec validation.

### 1. Run the test sweep

```bash
uv run python -m pytest packages -q
uv run ruff check
uv run python -m compileall -q packages velmor
```

Record PASS or FAIL per item with the key output line.

### 2. Exercise the invariants directly

Where the existing suite does not already cover an invariant, exercise it with a
throwaway script under the tests directory (not a committed test unless the task
asked for one) and record the observed value. Examples of the shape:

- Invariant 1: feed a `LicenseMatrix` an unknown string and assert the resolved
  grant is `None` and the resulting decision is not `PUBLISHABLE`.
- Invariant 4: iterate every non-`PUBLISHABLE` decision the suite produces and
  assert each carries at least one reason.
- Invariant 6: build the same input twice, run the gate twice, assert the two
  verdicts are equal and that `ENGINE_VERSION` is recorded on both.

Do not assert an invariant by reading the implementation. The point of this command
is an observed value.

### 3. Confirm the agent boundary

When an agent package changed, grep the graph for any call path that reaches the
storefront, the persistence layer's publish path, or a payment provider. A node may
write state and evidence; publishing happens after the graph completes, in the
runner. Report any node that breaks this.

### 4. Report and route

- **PASS** — every item green. State the coverage: how many test modules, how many
  invariants exercised directly, and which invariants were covered by an existing
  test rather than by this run.
- **FAIL** — per failure: the module or invariant, the symptom, and the traceback
  line or observed value. Hand the list to the `/ship` fix loop (resume the
  implementer, scoped re-review, then re-run `/rights-verify` on the affected
  surface only).

## Limitations — state these, do not hide them

- Unit tests use fakes for HTTP and for the store. They prove wiring and logic, not
  that Openverse is reachable or that Saleor accepts the payload. A run that never
  touches the live API must say so.
- An eval run needs a live model and is opt-in (`-m eval`). If a prompt changed and
  the eval was not run, report the eval as NOT RUN rather than as passing.
- The invariant sweep is only as good as the inputs it is given. If a new licence
  family was added without a test input, the sweep cannot see it — say so.

## Output

```
## Rights verification

**Impact surface:** <shared change -> full sweep | local change -> N modules>
**Packages:** services / auditor / scout / core / velmor

### Coverage
- [PASS] test_publication_gate.py — 12/12 (evidence: ...)
- [PASS] invariant 4 — every refusal carries a reason (exercised directly)
- [FAIL] invariant 1 — unknown licence resolved to PAID_OK (observed: ...)

### Not covered
- <item> — <why>

### Verdict
PASS / FAIL (N failures -> routed to fix loop)
```

## Guardrails

- Never assert an invariant from reading the code. Observe a value.
- Never widen a policy table or a test input to make the sweep pass. A failing
  invariant is the finding.
- If a fix would need the gate to refuse less, stop and ask the human — the hook
  `policy-guard.cjs` will ask on the edit, and that answer does not transfer to the
  sweep.
- Report NOT RUN distinctly from PASS.
