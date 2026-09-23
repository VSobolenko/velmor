---
name: "/improve-harness"
id: "improve-harness"
category: "Workflow"
description: "Turn a repeated agent failure into a rule, a skill, a sensor or a spec change"
---

# /improve-harness

When agents make the same class of mistake more than once, the fix is not another
one-off correction. The fix is the environment: a constraint the next agent cannot avoid.

Use this after `/diagnose` has found the root cause, or when the same defect appears in
two different changes.

## When

- The same mistake appears in two or more sessions, or in two or more changes.
- A gate or reviewer catches a class of bug that implementers keep reintroducing.
- A new external constraint appears (an API contract changed, a policy changed).

## Steps

1. **Write the failure down first**, in `harness/lessons.md`, using the template there:
   symptom, root cause, fix class, change made. Append-only.

2. **Choose the strongest fix the failure allows**, in this order:

   | Fix class | Use when | Reaches |
   |-----------|----------|---------|
   | `AGENTS.md` | The convention must bind every agent, including Codex | All agents, free |
   | Hook in `.cursor/hooks/` | The constraint is mechanically decidable on a write or a command | Every action, deterministically |
   | Sensor (`scripts/harness-status.mjs`, `scripts/selftest.mjs`, a test) | The defect is observable after the fact | CI and `/ship` |
   | Skill in `.cursor/skills/` | The knowledge is procedural and only needed sometimes | Agents that load it |
   | Rule in `.cursor/rules/` | The convention is for this repository's agents, always on | Cursor agents only |
   | `openspec/config.yaml` | The constraint belongs in the product contract | Proposal, spec, apply, archive |

   Prefer a mechanism over a sentence. A rule that says "be careful" was already tried.

3. **Add the regression check** in the same change: an assertion in
   `scripts/selftest.mjs`, a line in `harness-status.mjs`, or a test. Prove it can fail by
   injecting the defect, then confirm it passes once the defect is gone.

4. **Re-run the sensors and record the delta.**

   ```bash
   node scripts/harness-status.mjs
   node scripts/selftest.mjs
   ```

5. **If the harness includes Python under `packages/`, the fix is not harness work**: it
   goes through OpenSpec like any other change.

## Guardrails

- Never weaken a check to make a failure go away. That converts a defect into a blind spot.
- Never let the fix be a sentence in a file nothing reads. If a check exists, wire it into
  `/ship` or CI; an unread file is decoration.
- `harness/lessons.md` is append-only. Correcting an old entry is a new entry that says so.
- Do not add a rule to `[tool.ruff.lint].select` in a different change from the one that
  removes its violations.
