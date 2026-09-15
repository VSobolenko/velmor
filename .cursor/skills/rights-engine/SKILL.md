---
name: rights-engine
description: The rights engine - how a good is decided publishable, what each domain model means, where the policy table lives, and the invariants a change must not break. Load before editing anything under packages/services/src/rights, domain, or screening, or when a verdict or gate decision is involved.
---

# rights-engine

The component the company is built on. A wrong `PUBLISHABLE` is legal exposure; a
wrong `DENIED` is a lost sale. Both are bugs, but only one is irreversible, and the
code is written so that the irreversible one takes a deliberate act.

Read `.cursor/rules/06-rights-engine.mdc` as well; that rule is canonical for
policy. This skill is the map of the code.

## The decision in one line

`Candidate` + `Evidence` -> `RightsResolver.resolve()` -> `RightsRecord` ->
`PublicationGate.decide()` -> `GateDecision`. Nothing reaches the storefront
without `publishable=True`.

## The modules

| File | What it owns |
|------|--------------|
| `packages/services/src/domain/rights.py` | `RightsAction`, `RightsVerdict`, `EvidenceKind`, `Evidence`, `RightsRecord` |
| `packages/services/src/domain/license.py` | `StorefrontListing`, `LicenseGrant` |
| `packages/services/src/domain/gate.py` | `GateDecision` |
| `packages/services/src/rights/license_grants.py` | `DefaultLicenseGrants.TABLE` - the policy table |
| `packages/services/src/rights/license_matrix.py` | `LicenseMatrix` - messy license string -> canonical grant, or `None` |
| `packages/services/src/rights/rights_resolver.py` | `RightsResolver` - does the license grant the requested actions |
| `packages/services/src/rights/publication_gate.py` | `PublicationGate` - the only door to the storefront |
| `packages/services/src/rights/engine.py` | `RightsEngine` - composition of the three above, wired in `Container` |
| `packages/services/src/screening/prohibited_screen.py` | `ProhibitedCategoryScreen` - refuses, never rewords |

## The vocabulary, exactly

- `RightsAction` - `RESELL`, `REDISTRIBUTE`, `MODIFY`, `SUBLICENSE`. The storefront
  requests `RightsEngine.STOREFRONT_ACTIONS` = `(RESELL, REDISTRIBUTE)`, because
  Velmor lists a work as it arrived and does not grant buyers rights it does not
  hold itself.
- `RightsVerdict` - `ALLOWED`, `DENIED`, `UNKNOWN`. Only `ALLOWED` can pass the
  gate. `UNKNOWN` is the default outcome for anything not provable.
- `EvidenceKind` - `SOURCE_API_FIELD`, `LICENSE_FILE`, `SPDX_MATCH`,
  `LLM_EXTRACTION`, `HUMAN_ATTESTATION`. Only the first, second and last count as
  source evidence (`PublicationGate.SOURCE_EVIDENCE_KINDS`, an allowlist). A
  `SPDX_MATCH` records that identity matching happened; it is not proof that the
  identity came from the source, because the string the matcher normalised can have
  come from a model.
- `StorefrontListing` - `PAID_OK`, `FREE_ONLY`, `NOT_LISTED`. Independent of
  `commercial_use_allowed`: copyleft licenses permit earning money but fail
  `storefront_listing`, because a buyer free to redistribute what they paid for
  voids the price.
- `RightsRecord.reason` is a single `str`. `GateDecision.reasons` is a `tuple`.

Do not invent synonyms for these. Specs and code use these names.

## What the gate actually checks

`PublicationGate.decide(spec, record)` accumulates reasons and returns
`publishable=not reasons`:

1. Source tier is not `C` (tier C rights are not machine-readable).
2. `record.verdict is RightsVerdict.ALLOWED`.
3. `record.license_id` is set and resolves in the policy table.
4. At least one evidence item whose kind is in `SOURCE_EVIDENCE_KINDS` exists.
5. At least one `SPDX_MATCH` evidence item exists (identity was matched).
6. The grant's `storefront_listing` is not `NOT_LISTED`.

A rejection is therefore always explainable. A `GateDecision` with
`publishable=False` and an empty `reasons` is a bug by construction.

The gate has no notion of confidence, so a low-confidence reading must be stopped
before it gets here: `packages/auditor/src/nodes/routing.py` sends an identity that
resolved from a model reading below `escalation_confidence` to review instead of
deciding. A resolved identity is an identity match, and a page quote is source
evidence, so without that check a hesitant guess would satisfy the gate.

## Engine versioning

`RightsResolver.ENGINE_VERSION` (`'1.1.0'`) is stamped into every `RightsRecord`.
Bump it in the same change whenever a verdict could change for identical inputs -
a policy or alias change, a new gate condition. A silent policy change is an
unauditable one.

## Invariants a change must not break

1. Deny by default: an unresolved license string returns `None` from
   `LicenseMatrix.resolve`, which becomes `UNKNOWN`, which is not publishable.
2. No fuzzy matching. If a string does not resolve to a canonical entry, it does
   not resolve. Never widen `LicenseMatrix.ALIASES` to make one item pass.
3. The verdict is a pure function of `(Candidate, LicenseGrant, evidence)`. No
   model, clock, randomness, network or filesystem read may influence it. Time is
   passed in by the caller (`decided_at`).
4. A model may contribute an `Evidence` record and nothing else. It never returns
   a verdict, and its record is never source evidence: an `SPDX_MATCH` derived from
   a model reading cannot by itself satisfy the gate. The `SOURCE_EVIDENCE_KINDS`
   allowlist is what enforces this, so a new `EvidenceKind` is untrusted until it
   is named there.
5. The gate is the only door. No bypass, not even for a free item.
6. Verdicts are append-only. A correction is a new record with a new timestamp and
   an author, never an edit.
7. `packages/services/src/rights/**` imports no LangGraph, no LLM provider, no
   connector, no agent package.

Invariants 1-6 are asserted by `/rights-verify`. Invariant 7 is asserted by
`packages/core/tests/unit/architecture/test_layering.py`. Run both before claiming
a rights change is done.

## Changing the policy table

`license_grants.py` decides what the company may legally sell. Editing it is a
policy decision, not a refactor:

- State the license concern and cite the license text.
- Get a human reviewer. `.cursor/hooks/policy-guard.cjs` will ask for one; that
  prompt is not to be waived to make a task go faster.
- Bump `ENGINE_VERSION`.
- Add a test asserting both the acceptance and the refusal path.

Never widen a table to make one specific item pass. If a good needs an exception
to be sellable, the answer is "refuse the good".

## Adding a license family

1. Add the `LicenseGrant` entry to `DefaultLicenseGrants.TABLE`.
2. Add its spellings to `LicenseMatrix.ALIASES` (the messy variants a source
   actually emits).
3. Bump `ENGINE_VERSION`.
4. Test: the canonical id and each alias resolve; a case the license does *not*
   grant returns `DENIED`; if it must not be sold, `storefront_listing` blocks it.
5. Run `/rights-verify`.
