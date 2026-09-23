---
name: ralph-loop
description: Filesystem-ledger grind loop for a stubborn task that keeps stalling mid-context. Fresh agent context each iteration, all state on disk. Use when a task has failed twice in the same context and the cause is context, not the code.
---

# Ralph loop

Sit on the loop, not in it. The failure this addresses is a task that is not blocked by
anything external - it is blocked because the context that understood it has filled with
attempts, and every further attempt is made by a context that is more confused than the one
before it.

## The loop

1. Persist the goal and the acceptance test in `.superpowers/sdd/<slug>/ralph.md`. Both are
   written before the loop starts, by hand, and do not change during it:
   - the one observable result (the same standard as a Codex prompt's "Outcome"),
   - the exact command whose output decides pass or fail.
2. Each iteration runs in a **fresh context** and reads only two things: the ledger, and the
   failing evidence from the last iteration. Not the previous conversation.
3. Do the smallest next action. Update the ledger. Exit the context.
4. The outer driver - `/ship`, or you as the controller - re-invokes until acceptance or the
   cap. The driver holds the loop; the iteration never loops itself.

## Back-pressure

A loop needs a sensor that can say no, or it is just repetition:

- Python behaviour: `uv run python -m pytest packages velmor -q`
- the verdict path: `/rights-verify`
- a buyer surface: `/ux-verify`
- the harness itself: `node scripts/harness-status.mjs` and `node scripts/selftest.mjs`

## Hard limits

- Cap at 8 iterations by default, and write the cap into `ralph.md` before starting. A loop
  without a human-visible cap is an unbounded spend.
- Two consecutive iterations that change nothing means the blocking assumption is wrong. Stop
  and re-plan; do not run a third.
- Exit either way with a written Ruling: what was tried, what the sensor said, and what the
  next owner is. "Still failing" is a result, and it belongs in the ledger rather than in an
  eleventh attempt.
- The loop never relaxes a rule to reach acceptance. If acceptance needs a rights rule bent,
  the task is wrong - stop and escalate to the human.
