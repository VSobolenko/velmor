---
name: harness-peers
description: Run Cursor and Codex as peers on one task - role assignment, worktree isolation, the fallback ladder and how to verify a peer's work. Use on /ship, or any task where a second model family is worth the cost.
disable-model-invocation: true
---

# Peer agents

Read and follow `harness/dual-agent.md`. This is the checklist.

## Checklist

- [ ] Roles assigned for this task only: Build, Surface, Verify, Adjudicate
- [ ] If two agents write, they have disjoint file lists or separate worktrees
- [ ] Constraints that are not in `AGENTS.md` were passed in `developer-instructions`
- [ ] A Verify role runs `--sandbox read-only`
- [ ] After any peer write: read the diff, then run the gate and quote its output
- [ ] Ledger updated under `.superpowers/sdd/<plan>/`
- [ ] A disagreement was adjudicated against `AGENTS.md` and the specs, with the ruling written down

## Which second agent

| Situation | Use |
|-----------|-----|
| Bounded mechanical edit, conventions matter | A Cursor subagent - it inherits the rules |
| Independent review from another model family | Codex, read-only |
| Work that runs for minutes | A durable Codex worker, never the MCP tool |
| A large investigation whose detail should not enter this context | A Codex worker or the `explore` subagent |
| Image generation | Codex - its built-in `image_gen` needs no API key |
| Anything touching `packages/services/src/rights/**` | Nobody, without an explicit human request |

## Non-negotiable

- A peer's self-report is not evidence. `DONE`, "tests pass" and a summary are claims.
- Codex writes are not intercepted by `secret-guard.cjs`. Read its diff before staging.
- Never combine `sandbox: danger-full-access` with `approval-policy: never`.
  `mcp-audit.cjs` denies it, and `scripts/codex-run.mjs` refuses the sandbox outright.
- Never merge, push or archive on a peer's word.

Detail: `harness/dual-agent.md` (protocol and ladder), `harness/codex-workers.md` (the
runner, the prompt contract, the classified failures),
`.cursor/skills/codex-second-agent/SKILL.md` (the Codex MCP tools and their cost).
