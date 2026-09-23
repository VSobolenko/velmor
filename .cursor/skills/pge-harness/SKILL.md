---
name: pge-harness
description: Planner-Generator-Evaluator loop for Velmor. Use on any non-trivial /ship so generation and grading stay separated, and so the generator is a Codex worker rather than the agent that will grade it.
---

# Planner-Generator-Evaluator

The separation is the point: an agent that writes the code and then grades it holds one set of
blind spots, and every "independent" check it runs shares them. Velmor's version of the pattern
is stricter than the generic one in exactly one place - the Generator is Codex by default.

| Role | Who | Output |
|------|-----|--------|
| **Planner** | `.cursor/agents/planner.md` after the human's idea | OpenSpec proposal, delta specs, `tasks.md`, design notes |
| **Generator** | a **Codex worker** (`scripts/codex-run.mjs`, prompt from `harness/codex/prompts/build-task.md`); `.cursor/agents/generator.md` only as the documented fallback | the diff, a worker handoff, the ledger |
| **Evaluator** | `/eval` (`.cursor/agents/evaluator.md`) plus `/review` (`bugbot` + `security-review`), plus `/rights-verify` and `/ux-verify` when the change touches those surfaces | scores and PASS / FIX / KILL - findings only |

## Rules

1. The Planner does not implement. It writes the contract and stops at plan approval.
2. The Generator does not grade itself as final. `DONE` is a claim; the diff is the evidence.
3. The Evaluator never patches. It reports findings and hands them back.
4. A failed evaluation returns to the **same** Generator - `codex-run.mjs resume --id <worker>`
   for a narrow follow-up - bounded at 5 rounds. Restarting a worker to escape a failure
   destroys the session that has the context to fix it.
5. Context resets between roles. The Evaluator runs in a fresh context; the Generator is a
   separate process on a different model family. Never grade work produced in this session
   without saying so.
6. The Generator is Codex unless the ladder in `AGENTS.md` was actually descended, and the rung
   and signal are named in the output.

## Where this shows up

- `/ship` steps 0 (Planner), 1 (Generator), 3c (Evaluator), 4 (final checkers).
- `harness/ambition.md` - why the separation is worth its cost here.
- `harness/dual-agent.md` - the Codex peer protocol and the fallback ladder.
