---
name: "/review"
id: "review"
category: "Review"
description: "Dispatch reviewer subagents (bugbot + security-review) as a verification gate"
---

Run the writer/reviewer gate: hand the current work to independent reviewer
subagents, collect their findings, and report a PASS / CHANGES REQUIRED verdict.
The reviewing agent does NOT rewrite code — it verifies and reports.

This is the "second agent" in the harness. Run it after `/opsx-apply` (or after any
significant edit) and before `/opsx-archive` or before telling the user the work is
done.

## Steps

1. **Determine the review scope (Diff)**

   Pick one, in order of preference:
   - The user names an OpenSpec change → `Diff: branch changes`; if the work is
     uncommitted, `Diff: uncommitted changes`.
   - Otherwise default to `Diff: uncommitted changes`.
   - Confirm with `git status --short` and `git diff --stat`, and report what is
     actually in scope before dispatching.

2. **Gather the spec and contract context**

   The reviewer must verify conformance, not style. Read the authoritative specs:
   - `openspec/specs/**/*.md` — the synced product contract.
   - If a change is active: its `proposal.md`, `specs/**`, `tasks.md`, and
     `openspec status --change "<name>" --json`.
   - `AGENTS.md` and `.cursor/rules/*.mdc`.
   - `.cursor/rules/06-rights-engine.mdc` whenever anything under
     `packages/services/src/rights/` or `screening/` changed.

   Note the fixed contracts the diff must not break:
   - The verdict is a pure function of its inputs; no model, clock or network on
     that path.
   - Deny by default: an unresolved licence is not a guess.
   - Nothing is publishable without `GateDecision.PUBLISHABLE`.
   - Every refusal carries at least one reason.
   - A verdict is append-only.
   - The import direction in `.cursor/rules/02-architecture-layers.mdc`.
   - The domain vocabulary in `packages/services/src/domain/` — no synonyms.

3. **Run lightweight verification as evidence**

   Do not claim a check passed without its output:
   - Python changed → `uv run ruff check` and `uv run python -m pytest packages -q`
   - Runtime sanity → `uv run python -m compileall -q packages velmor`
   - Rights, screening, connectors or the gate changed → also run `/rights-verify`
   - Spec or planning changed → `openspec validate --strict "<change-name>"`

   Report each result as pass/fail with the key line.

4. **Dispatch the reviewer subagents (in parallel, one message)**

   Launch exactly one `bugbot` and exactly one `security-review` subagent via the
   Task tool, both with `run_in_background: false`, using these exact contracts:

   - **bugbot** — description exactly `Bugbot`, prompt:
     ```
     Full Repository Path: <repo root>
     Diff: <uncommitted changes | branch changes>
     Change Description: <one line on what this work does>
     Custom Instructions: Verify the diff conforms to the OpenSpec specs in
     openspec/specs/ and to .cursor/rules/06-rights-engine.mdc, 02-architecture-layers.mdc
     and 05-agent-graphs.mdc. Specifically: is any model, clock or network call on
     the path from evidence to RightsVerdict; can an unresolved licence reach
     PUBLISHABLE; does every non-publishable GateDecision carry at least one reason;
     has any import broken the allowed layer direction; is any node non-idempotent
     under a checkpoint resume. Flag spec drift and broken contracts with file paths
     and line numbers, not style.
     ```
   - **security-review** — description exactly `Security Review`, prompt:
     ```
     Full Repository Path: <repo root>
     Diff: <uncommitted changes | branch changes>
     Custom Instructions: Follow .cursor/rules/01-security-secrets.mdc. Check for
     hardcoded credentials, secrets reaching logs, unvalidated external input from
     a source connector or a fetched page, and prompt-injection exposure in text
     that is fed to a model. Treat an unpinned or unvetted new dependency as a
     finding, not a suggestion.
     ```

   Launch both in a single message so they run in parallel.

5. **Triage with technical rigour, not performative agreement**

   For each finding decide whether it is:
   - **Blocking** — real spec drift, a broken invariant, a secret, a failing check.
   - **Non-blocking or a false positive** — a pre-existing issue outside the diff, or
     a suggestion that conflicts with a fixed convention.

   Do not accept every suggestion. If a reviewer's claim conflicts with the spec or a
   convention, say so and why it is not applied. When a finding claims the gate
   allows something it should refuse, prove it with a test input before accepting or
   rejecting it — that class of claim is never resolved by reading the diff alone.

6. **Report a verdict — the gate**

   - **PASS** — no blocking findings and every verification check green. State that
     the work is ready for `/opsx-archive`.
   - **CHANGES REQUIRED** — list blocking findings (file, line, what to fix) grouped
     by reviewer. Do not fix them here; hand the list back to the writer.

   `/review` produces a verdict and evidence, nothing else. Do not archive or claim
   success on the strength of this command alone.

## Output

```
## Review

**Scope:** <uncommitted changes | branch changes> (<N> files)
**Spec basis:** <list of specs consulted>

### Verification
- ruff: <pass/fail + line>
- pytest: <pass/fail + line>
- rights-verify: <pass/fail + line or n/a>
- openspec validate: <pass/fail + line>

### Findings
- [blocking|non-blocking] <file:line> — <description> (reviewer)

### Verdict
PASS / CHANGES REQUIRED
```

## Guardrails

- Never rewrite code in this workflow. Report only.
- Capture real command output before asserting a check passed.
- Always launch both reviewers unless the user explicitly says to skip one.
- Do not treat a reviewer's claim as true without checking it against the spec.
- Keep the diff scope explicit; the reviewers must know what is in and out.
- A claim that the gate has stopped refusing is verified with a test input, never
  with reasoning about the diff.
