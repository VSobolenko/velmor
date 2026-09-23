---
name: "/diagnose"
id: "diagnose"
category: "Workflow"
description: "Find the root cause of a harness, tooling or agent failure before changing anything"
---

# /diagnose

Use when a command, a hook, an MCP server, a subagent or the Codex channel misbehaves.
Do not edit things to see what happens; form one hypothesis and test it.

Follow `.agents/skills/systematic-debugging/SKILL.md`. Root cause first.

## Steps

1. **Reproduce it and keep the output.** The exact command, the exact failure. If it only
   happens sometimes, say what differs between a run that fails and one that does not.

2. **Run the harness sensors.**

   ```bash
   node scripts/harness-status.mjs
   node scripts/selftest.mjs
   node scripts/setup-mcp.mjs
   ```

3. **Narrow by failure class.**

   | Symptom | Look at |
   |---------|---------|
   | A rule or convention was ignored | Is it in `AGENTS.md`? Codex reads only that. A rule that lives solely in a `.mdc` file does not reach an external agent. |
   | A write was denied | Which hook? Every hook prints its own reason on stdout. Read it and fix the cause. Do not work around it. |
   | A hook never ran | `hooks.json` event name, matcher, and the script path in `.cursor/hooks/`. `node scripts/harness-status.mjs` checks that every referenced script exists. |
   | An MCP tool is missing | `node scripts/setup-mcp.mjs`; the server must also be enabled in Cursor Settings -> MCP and the window reloaded. |
   | A Codex worker produced nothing | `node scripts/codex-run.mjs status` then `log --id`. A `BLOCKED(...)` signal is classified, not a mystery; the ladder is in `harness/dual-agent.md`. |
   | A subagent did not trigger | Its `description` is what the parent reads. Make it say when to use it, not what it is. |
   | The same defect as last week | `harness/lessons.md`. If it is there, the fix was never made mechanical. |

4. **Record the root cause.** A one-off diagnosis goes in `.velmor/diagnose/<topic>.md`.
   A recurring failure goes to `/improve-harness`, which appends to `harness/lessons.md`
   and adds the regression check.

## Guardrails

- Do not silence a failure to make it stop. A hook that is failing is working; a test that
  is failing is telling you something.
- Do not add a `try/except` around the failing call. `.cursor/rules/03-error-handling.mdc`
  is canonical and this command is not an exemption.
- If the cause is outside the repository, report BLOCKED with the command and the output.
  Do not guess and do not paper over it.
