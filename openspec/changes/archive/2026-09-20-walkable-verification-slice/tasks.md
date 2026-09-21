# Tasks

Ordered so the deterministic layer is complete and tested before anything depends
on it. Tests belong to the task that adds the behaviour, not to a trailing task.

## 1. Pass report models

- [x] Add `VerificationOutcome` (published, refused, screened out, paused) and
      `VerificationRun` to `packages/services/src/domain/`, following the shape of
      `scout_run.py`: frozen, fields only, no behaviour and no computed properties.
      `VerificationRun` carries the run id, one outcome per candidate with its
      reasons, and the refusal counts per prohibited category.
- [x] Tests: a run with one candidate per outcome is representable and each
      outcome keeps its own reasons; a screened-out outcome carries no
      `GateDecision`; a paused outcome carries no decision either.

## 2. Screen before the rights path

- [x] In `AuditorRunner`, screen each selected candidate with
      `ProhibitedCategoryScreen` before invoking the graph. A match produces a
      screened-out outcome carrying the matched terms as reasons and the graph is
      not invoked for that candidate.
- [x] Tests: a prohibited candidate yields no rights record and the graph is not
      invoked for it (assert the graph was untouched, not merely that the result
      is a refusal); a clear candidate proceeds unchanged; a reworded title does
      not change the refusal.

## 3. Aggregate the pass

- [x] `AuditorRunner.run_once()` returns a `VerificationRun` instead of a tuple of
      decisions, distinguishing published, refused, screened out and paused, and
      leaving the existing save behaviour for decisions unchanged.
- [x] Count refusals per category so the pass can report which categories refused
      what.
- [x] Tests: every candidate in the batch appears exactly once in the report; a
      batch of ten with three prohibited reports three refusals and verifies the
      other seven; a candidate whose graph run pauses is reported as paused with
      no decision and does not stop the rest of the batch.

## 4. Node tests

- [x] One test per node with a hand-built `AuditorState`:
      `collect_declared_evidence` (tier A declared licence recorded as source
      evidence; tier B and absent licence record nothing),
      `resolve_license` (claim precedence human ruling over model reading over
      declared field; an unresolvable claim resolves to nothing and adds no
      identity match), `investigate` (attempts increment; the page quote and the
      model claim are recorded as their own kinds), `review` (a rejected ruling
      resolves nothing; an approval adds a human attestation and, when it
      resolves, an identity match, without widening what the licence permits),
      `decide` (the accumulated evidence reaches the same verdict when the node is
      re-run).
- [x] Routing table test: one case per branch of `ResolutionRouter` - resolved
      goes to decide, unresolved with attempts remaining goes to investigate,
      attempts exhausted goes to review - plus a resolved-but-uncertain reading
      going to review.
- [x] Assert the graph compiles with no network, no model and no database.

## 5. Path test

- [x] Walk the whole path with a fake connector, a fake page fetch, a fake
      interpreter and the in-memory store: discovery stores a candidate, the pass
      screens it, the graph resolves or investigates it, and the gate decides it.
      Assert one publishable candidate and one refused candidate, with the refusal
      carrying at least one reason.
- [x] Assert a second pass does not re-verify a candidate that already has a
      rights record.
- [x] Assert a source that raises during discovery is reported as a failure while
      the run still completes, and that a payload which cannot be interpreted
      stores no partial candidate.

## 6. Discovery tests

- [x] Tests for `packages/scout`: every enabled source is queried once per term and
      a disabled source is neither queried nor reported as queried; the same
      candidate seen in two passes exists once; a candidate declaring a
      non-commercial licence is stored and receives no rights decision; a source
      reporting no licence stores the candidate with the licence absent.
- [x] Assert a source failure leaves the other source's candidates stored.

## 7. Report from the CLI

- [x] `velmor/agents/auditor.py` prints the pass report: totals per outcome, the
      refusal counts per category, and one line per candidate with its outcome and
      reason. Keep the existing `once` and `loop` commands and the existing
      per-candidate detail.
- [x] Tests: the printed summary counts match the report, and a paused candidate
      is reported as paused rather than as a refusal.

## 8. Documentation

- [x] Update the "Current state" section of `AGENTS.md`, and the pass-report term
      in `.cursor/skills/agent-graph/SKILL.md` if it names the runner's return
      value.
- [x] Note the new capability in `README.md` if its status list changes.

## 9. Verification gate

Not a code task: the evidence that the change is done.

- [x] `uv run ruff check` and `uv run python -m pytest packages velmor -q` both
      clean (161 passed; `ruff check` clean after `quote-style = "single"` and the
      `.agents` exclusion were added, without which `ruff format` would have
      rewritten every string in the repository).
- [x] `uv run python -m compileall -q packages velmor` clean.
- [x] `openspec validate --strict walkable-verification-slice` passes.
- [x] `/rights-verify` sweep run: invariants 1-4 and 6-9 observed green, invariant 5
      (no bypass) NOT RUN because no publish path exists yet, and reported as NOT
      RUN rather than as passing.
- [ ] One manual live pass against Openverse, with its output quoted, since no
      automated test touches the network. Not done: it needs the Postgres
      checkpoint database, a filled `packages/<agent>/.env.dev` and `OPENAI_API_KEY`,
      and nobody has run this path against the real API yet. Until it is run, the
      Postgres store, the checkpointer and the Openverse payload mapping are
      unproven.
