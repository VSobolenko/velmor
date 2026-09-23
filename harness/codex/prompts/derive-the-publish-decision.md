# derive-the-publish-decision: a publication decision is derived, never asserted

## Outcome

`velmor publish` no longer builds a `GateDecision` by hand: it hands the bridge a decision the
gate itself produced. `PublicationBridge.apply` re-derives the ruling from `spec` and
`decision.record`, so a caller that asserts `publishable=True` for a record the gate refuses is
refused with `RightsDeniedError` and no entry is written, while a caller that passes
`publishable=False` still takes the existing withdraw-or-report path with the gate's reasons. A
ruling recorded by an engine other than the running one is reported as a reason on the outcome and
does not change the action.

## Scope

Working root: the repository root (`d:\Python\Velmor`).

Read first, in this order:
- `AGENTS.md` - the always-on contract, including the rights rules that bind you
- `openspec/changes/derive-the-publish-decision/proposal.md`, `design.md`, `tasks.md` - this task's
  contract. Tasks 1.1, 1.2 and 1.3 are yours. Do not do 2.1, 2.2, 3.1 or 3.2: the rule text, the
  harness sensor and the gates belong to another agent.
- `openspec/changes/derive-the-publish-decision/specs/commerce/catalog-publication/spec.md` - the
  three requirements and their scenarios; that file is the acceptance criteria
- `packages/services/src/domain/gate.py`, `packages/services/src/rights/publication_gate.py`,
  `packages/services/src/rights/rights_resolver.py`, `packages/core/src/errors.py`
- `packages/services/src/commerce/publication.py`, `velmor/publish.py`
- `packages/services/tests/unit/commerce/test_publication.py`,
  `velmor/tests/unit/test_publish_command.py`

Write only these files:
- `packages/core/src/errors.py`
- `packages/services/src/commerce/publication.py`
- `velmor/publish.py`
- `packages/services/tests/unit/commerce/test_publication.py`
- `velmor/tests/unit/test_publish_command.py`

Nothing else. Do not add a file that is not listed, and do not edit `scripts/`, `.cursor/`,
`harness/` or `openspec/`.

## Inputs

- `PublicationGate.decide(spec, record)` is a pure function of its inputs: same `spec`, same
  record, same ruling, every time. It is called in production today only from
  `packages/auditor/src/nodes/decide.py`.
- `RightsDeniedError` lives in `packages/core/src/errors.py` and is never raised anywhere in the
  repository yet. Its docstring currently says "A good was about to be published without a
  passing rights verdict."; narrow it to the case the guard now covers - a decision that claims
  publishable while the gate's own ruling refuses.
- `RightsResolver.ENGINE_VERSION` is the running engine version. Import it; never copy the string.
- The cheapest record the gate refuses, needing no new fixture machinery, is one whose evidence is
  empty or carries no `SOURCE_EVIDENCE_KINDS` member: it trips `_check_evidence`. Check what
  `build_record` in the existing test modules already gives you before writing a new helper.
- Backwards compatibility is not a concern: nothing but this repository calls the bridge.

## Hard rules

- Do not run git. Do not create, amend or push a commit.
- Do not touch a `.env` file, a credential, or anything under `.velmor/`.
- No `try/except`. It is forbidden in this repository unless the task explicitly authorizes a
  specific exception and names the class; see `.cursor/rules/03-error-handling.mdc`. If you believe
  one is required, reply `BLOCKED` with the reason instead of writing it. This change adds a
  `raise`, never a `catch`.
- Do not edit anything under `packages/services/src/rights/` or
  `packages/services/src/screening/`. Do not change any gate condition, license grant, alias table
  or `ENGINE_VERSION`.
- Preserve the rights contract: nothing is publishable without a `PUBLISHABLE` gate decision, and a
  non-`PUBLISHABLE` decision keeps its reasons. `PublicationAction` keeps its existing values.
- A decision that is not publishable is a value, not an error. Only the assertion case raises.
- Match the surrounding style: `from __future__ import annotations`, ruff line length 100, sorted
  imports, logic in class methods, no truthiness defaults, no optional accessors.
- Do not refactor a neighbour, rename a symbol, or "clean up while here".

## Verification boundary

Run exactly these, from the repository root, and nothing else:

- `uv run ruff check`
- `uv run python -m pytest packages velmor -q`

Do not retry a failure. Run each once; if it fails, that is the result to report.
No network commands at all: no `uv sync`, no `pip`, no `docker`, no database, no `npm`.

Additionally, and this is required rather than optional: prove the guard can fail. Temporarily make
the bridge trust `decision.publishable` again, run
`uv run python -m pytest packages/services/tests/unit/commerce/test_publication.py -q`, watch the
new raising case fail, restore the derivation, run it again and watch it pass. Quote both runs in
your handoff. A check that has not been seen failing is not evidence.

## Budget

Keep this well inside your context; reserve enough to run the two commands above and write the
handoff. If the work cannot be finished without dropping scope, reply exactly `CONTEXT_LIMIT`
rather than guessing or silently narrowing the task.

## Reply contract

On success: `DONE <comma-separated files changed>`
On failure: `BLOCKED <one-line reason>`
