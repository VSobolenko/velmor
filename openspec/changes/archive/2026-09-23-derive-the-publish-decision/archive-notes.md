# Archive notes - `derive-the-publish-decision`

## Effect on what Velmor may publish

The change only narrows publication, and only for a caller that was already wrong.

`GateDecision` is no longer something a caller may build and hand to the bridge.
`PublicationBridge.apply` re-derives the gate's own ruling from the decision's
record and raises `RightsDeniedError` when the caller's decision claims the record
is publishable while the gate refuses it. A decision that is not publishable is
unchanged behaviour: the outcome is reported, or an existing entry is withdrawn,
carrying the gate's reasons. Nothing was added to the licence policy table, no
policy entry was relaxed, and no refusal was removed. No good became publishable
that was not publishable before; a good whose decision contradicts the gate stops
producing an entry instead of producing one.

`velmor/publish.py` is the caller that motivated this: it built a
`GateDecision(publishable=True)` by hand and handed it to the bridge, which meant
the published state could disagree with the gate's own ruling with nothing
detecting it. It now calls `gate.decide(spec, record)`, so the decision the bridge
receives is the gate's output.

A ruling recorded by an engine other than the running one is now reported as a
reason on the outcome. It is deliberately not a refusal: every record on sale
predates the running engine, so refusing would withdraw the catalogue over a
divergence only a re-decision could act on. The action taken is unchanged.

## Engine version

`RightsResolver.ENGINE_VERSION` did not move - it is `1.2.0` before and after this
change. The change touches the publication path and the reporting of a version
mismatch, not the verdict path: no licence policy input changed, so no stored
ruling's outcome changes, and no re-audit was required by this change.

## Effect on the buyer surface

None. No page, locale, copy, layout or image changed, so `/ux-verify` does not
apply to this change. What a buyer sees is unaffected; what decides whether a good
reaches the shop is not.

## Verification recorded at archive time

`/rights-verify` was run and returned PASS: the impact sweep reported `340 passed`,
invariant 5 was observed through `TestCallerAssertionTheGateContradicts`
(`3 passed in 0.40s`) rather than by reading the code, invariant 7 through
`test_layering.py` (`14 passed`), invariants 1, 2, 4 and 6 were exercised directly
with real gate inputs, and invariant 3 was observed at the listing boundary
(`GPL-3.0-only` is publishable with `listing=free_only`; the bridge refuses to sell
it). Standing gates: `ruff` -> `All checks passed!`, `pytest packages velmor -q` ->
`730 passed`, `compileall` -> exit 0, `openspec validate --strict` -> valid,
`harness-status.mjs` -> `VERDICT: READY`.

Two things were NOT reproduced in the archive session and are recorded as the
earlier session's, not this one's:

- The injected-defect round for the bridge guard (tasks 1.1 and 2.2): restoring
  `decision.publishable` as the source of truth and quoting the failure. `codex-gate`
  correctly refused a Cursor write to `packages/services/src/commerce/publication.py`,
  and the gate was deliberately not bypassed to inject the defect. The checks pass;
  that they can be made to fail was shown when they were written.
- The re-audit of the stored records (task 3.2). The `105 publishable / 0 refused`
  figure is the earlier run's and was not re-confirmed here.

Every task in `tasks.md` carries a `Verified 2026-09-23:` line naming what was
observed and what was not, so that file is a record of what was checked rather than
a list of intentions.
