---
name: harness-improve
description: Turn a repeated agent failure into a permanent constraint - a hook, a sensor, a rule or an AGENTS.md line. Use after /diagnose, or when the same defect appears twice.
---

# Improve the harness

Follow `/improve-harness`. Follow `.cursor/rules/08-evidence-and-sensors.mdc`: a sensor that
cannot fail is not a sensor, and a rule that only says "be careful" was already tried.

## The order that matters

1. `AGENTS.md` - the only channel that reaches Codex for free.
2. A hook in `.cursor/hooks/` - use when the constraint is mechanically decidable.
3. A sensor - `scripts/harness-status.mjs`, `scripts/selftest.mjs`, or a test.
4. A skill - procedural knowledge, needed only sometimes.
5. A rule in `.cursor/rules/` - always-on for Cursor agents only.
6. `openspec/config.yaml` - the constraint belongs in the product contract.

## Then

- Add the regression check in the same change, and prove it can fail by injecting the
  defect.
- Append to `harness/lessons.md`. It is read at session start, so an entry is how the
  harness remembers.
- Re-run `node scripts/harness-status.mjs` and `node scripts/selftest.mjs`, and record the
  delta.

## Anti-patterns

- A paragraph added to a file nothing reads. If a check exists, wire it into `/ship` or CI.
- A sensor whose failure mode has never been observed. Inject the defect first.
- Relaxing a check so a failure stops appearing. That converts a defect into a blind spot.
- Copying another project's harness wholesale. Take the pattern; adapt the content.
