---
name: "/eval"
id: "eval"
category: "Review"
description: "Independent Evaluator role: grade a change against a fixed rubric. Never self-grade"
---

# /eval - Planner-Generator-Evaluator: the Evaluator

The **Evaluator** does not write product code. It grades the artefact against a fixed
rubric, in a fresh context, preferably from a different agent family than the one that
built it: Codex if Cursor built it, `bugbot` plus `security-review` if not.

The point of the separation is that a reviewer with the author's context shares the
author's blind spots. A green suite written by the author cannot see what the author did
not think to check.

## Rubric - score each 0-5, the bar is all scores >= 4

1. **Rights invariants.** Is the verdict still a pure function of its inputs? Can an
   unresolved licence reach `PUBLISHABLE`? Does every non-publishable `GateDecision` carry
   at least one reason? Was `ENGINE_VERSION` bumped if a verdict could change for identical
   inputs? Read `.cursor/rules/06-rights-engine.mdc` and check the refusal path, not just
   the acceptance path.
2. **Evidence.** Is every claimed pass backed by output the Evaluator reproduced itself?
   A self-report is not evidence, including one from this session.
3. **Architecture.** Does the diff respect the fixed import direction in
   `.cursor/rules/02-architecture-layers.mdc`? Does `packages/services` stay free of the
   agent stack?
4. **Tests.** Is there a test that fails without the behaviour the task added? Run it with
   the behaviour disabled to check, or explain why that is not applicable.
5. **Buyer surface.** If anything a buyer reads or acts on changed: do screenshots exist
   for every affected route at desktop and mobile width in every locale, and does every
   string come from the locale dictionaries?
6. **Honesty.** Do the specs, the archive note and the listing describe what the code
   actually does? A requirement satisfied by a text dump is a finding.
7. **Scope.** Is the diff the smallest change that satisfies the task? Refactors of
   neighbours, reformats of untouched files and "clean up while here" are findings.

## Steps

1. Scope the change: the OpenSpec change, its `tasks.md`, and the diff under review.
2. Run the objective gates yourself and capture the real output:

   ```bash
   uv run ruff check
   uv run python -m pytest packages velmor -q
   uv run python -m compileall -q packages velmor
   ```

   Plus `/rights-verify` if rights, screening, connectors or the gate changed, and
   `/ux-verify` if a buyer-facing surface changed. Dispatch `/review` for the independent
   reviewers, and consider a read-only Codex worker (`node scripts/codex-run.mjs review`)
   as a third opinion from a different model family.
3. Write the result to `.velmor/eval/<change>.md`: per-criterion score, the finding list,
   and a verdict of **PASS**, **FIX** or **KILL**.
4. On FIX, hand the findings to the Generator. The Evaluator does not patch.

## Guardrails

- Never grade work you wrote in this session. If the same agent must grade it, say so
  explicitly and treat the score as lower confidence.
- Never show the Generator the reasoning behind a score, only the finding list. A score
  that comes with an argument trains good behaviour; a score that argues back invites
  negotiation with the rubric.
- Never issue PASS on the strength of the test suite alone. The suite proves the covered
  behaviour; it says nothing about a rendered page and nothing about a verdict that
  changed for identical inputs.
- A claim that the gate now allows something it used to refuse is verified with a test
  input, never by reading the diff.
