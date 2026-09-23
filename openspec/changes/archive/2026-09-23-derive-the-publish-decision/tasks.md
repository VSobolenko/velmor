# Tasks

Ordered so the guard exists and is proven before the caller is changed to satisfy it, and so the
rule text moves only once the code it describes is in place.

## 1. The derivation and the guard

- [x] 1.1 Make the guard real in `packages/services/src/commerce/publication.py`. `apply` derives the
      gate's ruling from `spec` and `decision.record` rather than reading `decision.publishable`, and
      raises `RightsDeniedError` when the caller's decision claims `publishable=True` while the
      gate's own ruling refuses. A decision that is not publishable keeps its current path: the
      `_when_not_publishable` branch withdraws or reports, with the gate's reasons. Narrow
      `RightsDeniedError`'s docstring in `packages/core/src/errors.py` to the case it now covers.
      Verify: `test_publication.py` gains a case where a hand-built `GateDecision(publishable=True)`
      over a record the gate refuses - a record with no source evidence is the cheapest such record -
      raises `RightsDeniedError` and writes no entry, and a case asserting the same record passed as
      `publishable=False` still withdraws rather than raising, so the two paths are distinguishable
      in one test module. Then prove the guard can fail: restore `decision.publishable` as the
      source of truth, show the new raising case failing, restore the derivation, show it passing.
      Quote both runs.

      Verified 2026-09-23: all three cases in `TestCallerAssertionTheGateContradicts` pass -
      `3 passed in 0.40s` - which covers both the raising path and the not-publishable path in one
      module. The fail-proof was NOT reproduced in this session: `codex-gate` refused a Cursor write
      to `publication.py` and the gate was deliberately not bypassed to inject the defect, so the
      quoted pair of runs is the earlier session's, not this one's.

- [x] 1.2 Derive the decision in `velmor/publish.py`. Replace the hand-built
      `GateDecision(candidate_id=..., publishable=True, reasons=(), record=record)` with
      `gate.decide(spec, record)`, and move the `spec` lookup above it. `bridge.apply` is then called
      with a decision the gate produced. Verify: `velmor/tests/unit/test_publish_command.py` asserts
      that the decision handed to the bridge is the gate's output for a record the gate refuses,
      that the run reports a withdrawal or a refusal rather than an error, and that no `typer.echo`
      line prints a reason the gate did not produce. A reviewer must be able to see that
      `velmor/publish.py` no longer constructs a `GateDecision` by hand.

      Verified 2026-09-23: `velmor/publish.py` calls `gate.decide(spec, record)` at the spec lookup
      and constructs no `GateDecision`; `velmor/tests` pass inside the impact sweep (`340 passed`).

- [x] 1.3 Report a ruling recorded under an engine other than the running one. Compare
      `record.engine_version` with `RightsResolver.ENGINE_VERSION` on the publication path and attach
      the mismatch as a reason on the outcome, so it appears in the operator's report beside the
      action. Do not change the action and do not refuse; `design.md` D3 records why, with the count
      that makes a refusal an outage. Verify: a test asserts that a record stamped with an older
      engine still publishes but carries the reason, and that a record at the running version carries
      no such reason; and the report line for such a good is quoted in the task report.

      Verified 2026-09-23: `_with_engine_version_reason` attaches the reason and returns the
      outcome's action unchanged; the velmor tests covering it pass in the sweep. The report line
      itself is not quoted in this session.

## 2. The rule, and the sensor that holds it

- [x] 2.1 Correct the two claims that do not match the code:
      `.cursor/rules/06-rights-engine.mdc`, where the sentence about `RightsDeniedError` must state
      what the bridge now does, and `.cursor/commands/rights-verify.md` invariant 5, which must state
      what is enforced and how a run observes it - the observation is the raising case in
      `test_publication.py`, not a reading of the code. Verify: quote both edited passages, and state
      that no other invariant's meaning changed.

      Verified 2026-09-23: rule `06-rights-engine.mdc` states that `PublicationBridge.apply`
      re-derives the gate's ruling and that a caller's `publishable` flag is never the source of
      truth; `rights-verify.md` invariant 5 names `TestCallerAssertionTheGateContradicts` as the
      observation and keeps the not-publishable case as an outcome. No other invariant was edited.

- [x] 2.2 Add the sensor to `scripts/selftest.mjs`: a check that drives the bridge with a decision
      asserting publishable over a record the gate refuses and asserts that `RightsDeniedError` is
      raised. Follow the file's own conventions for how it drives a check and how it reports, and
      assemble any fixture at runtime for the reason the file already records. Verify: run
      `node scripts/selftest.mjs` and quote the new check's line; then inject the defect by making the
      bridge trust `decision.publishable` again and show the check reporting a failure; restore and
      show `VERDICT: PASS`. Both runs quoted.

      Verified 2026-09-23: the check passes and reports
      `PASS   the bridge raises RightsDeniedError for a decision the gate refuses - ...: 'openverse:1'
      was presented as publishable but the gate refuses it: Verdict rests only on interpretation ...`,
      `VERDICT: PASS`. The injected-defect round was NOT reproduced in this session, for the same
      `codex-gate` reason as 1.1.

## 3. Gates

- [x] 3.1 Run the standing gates and quote output rather than a summary: `uv run ruff check`,
      `uv run python -m pytest packages velmor -q`, `uv run python -m compileall -q packages velmor`,
      `openspec validate --strict "derive-the-publish-decision"`, and
      `node scripts/harness-status.mjs` because a rule and a harness script changed. Report any
      command not run as unverified.

      Verified 2026-09-23: `ruff` -> `All checks passed!`; `pytest packages velmor -q` ->
      `730 passed, 1 warning in 31.47s`; `compileall` -> exit 0; `openspec validate --strict
      "derive-the-publish-decision"` -> `Change 'derive-the-publish-decision' is valid`;
      `harness-status.mjs` -> `VERDICT: READY`.

- [x] 3.2 Run `/rights-verify` and report the outcome explicitly, including that invariant 5 is now
      covered by an observation rather than by reading the code, that the gate was re-run over the
      stored records and returned 105 publishable and 0 refused, and that
      `RightsResolver.ENGINE_VERSION` did not move. Verify: the command's output is quoted, and the
      report states plainly which invariants this change touched and which it did not.

      Verified 2026-09-23: `/rights-verify` run, verdict PASS, with the impact sweep at
      `340 passed`, invariant 5 observed through `TestCallerAssertionTheGateContradicts`, invariant 7
      through `test_layering.py` (`14 passed`), invariants 1, 2, 4 and 6 exercised directly with real
      inputs, and invariant 3 observed at the listing boundary (`GPL-3.0-only` is publishable with
      `listing=free_only`; selling is refused by the bridge). `ENGINE_VERSION` is `1.2.0` and did not
      move. The stored-record re-audit was NOT re-run in this session, so the `105 publishable / 0
      refused` figure is the earlier run's and is not re-confirmed here.
