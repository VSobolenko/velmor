---
name: "/harness-status"
id: "harness-status"
category: "Workflow"
description: "Report whether the agent harness is complete and consistent: surfaces, mirrors, hooks, MCP, Codex channel, OpenSpec"
---

# /harness-status

The harness is a set of files that fail silently. This command runs the sensors that make
the silent failures loud.

## Steps

1. **Harness health**

   ```bash
   node scripts/harness-status.mjs
   ```

   One line per fact: `PASS`, `WARN`, `INFO` or `FAIL`. `WARN` means this machine cannot
   exercise part of a correct harness (no Docker, no Codex CLI) - it is not a defect in
   the repository. `FAIL` means the harness is incomplete or internally inconsistent.

2. **Harness scripts honour their own contract**

   ```bash
   node scripts/selftest.mjs
   ```

   This drives the harness scripts against injected defects. A sensor that cannot fail is
   not a sensor, and this is where that is checked.

3. **MCP resolution**

   ```bash
   node scripts/setup-mcp.mjs
   ```

   Names the package behind every alias, the environment variables a server needs, and
   fails on an alias that is not in `.cursor/mcp/mcp-aliases.cjs` or a credential written
   into the config instead of interpolated.

## Report

```
## Harness status
- harness-status: <READY | NOT READY> (<n> PASS, <n> WARN, <n> FAIL)
- FAIL lines: <each path and what is wrong>
- selftest: <pass/fail + key line>
- setup-mcp: <every launcher resolves | the misconfiguration>
- Codex channel: <resolved binary version | unresolved>
- Active OpenSpec changes: <names>
```

Do not repair anything here. A `FAIL` is either a missing file to create or a drift to
reconcile; route to `/diagnose` when the cause is not obvious from the line itself.

## Guardrails

- Quote the real output. A summary of a status script that was not run is not a status.
- A `WARN` is reported as a `WARN`, not rounded up to a pass and not rounded down to a
  failure.
- `.cursorignore` is required by `harness-status.mjs` and cannot be written by an agent
  (the environment denies writes to it). If it is the only `FAIL`, say so and hand the
  content to the human instead of working around the denial.
