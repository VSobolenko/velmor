#!/usr/bin/env node
/**
 * beforeMCPExecution - the one MCP policy a machine can decide.
 *
 * What this is for
 * ----------------
 * `.cursor/skills/codex-second-agent/SKILL.md` states a rule that nothing enforced:
 * "Never combine `sandbox: danger-full-access` with `approval-policy: never` on an
 * unattended run. That is an unrestricted agent with no guardrails." A rule in a skill
 * is advice; an agent that decides the combination is convenient can still ask for it.
 * This hook is the enforcement, because the parameters of that decision are structured
 * and unambiguous.
 *
 * It is deliberately narrow. A broad "dangerous tool name" filter is theatre: it fires
 * on names it cannot interpret and misses the call that matters. The two checks here
 * are exact.
 *
 *   1. `codex` / `codex-reply` with `sandbox: danger-full-access` and
 *      `approval-policy: never` - denied.
 *   2. A tool whose name asks to destroy a host resource (`wipe_device`, `format_disk`)
 *      - denied. Nothing configured for this repository legitimately does that, so a
 *      match means the server is not the one it claims to be.
 *
 * Everything else is allowed, including full details on the denial so the agent can
 * retry with a sandbox that is not the problem.
 *
 * Contract: MCP-call JSON on stdin, permission JSON on stdout, exit 0. It must never
 * throw, because a crashed `beforeMCPExecution` hook is read as a hook failure and the
 * action then depends on `failClosed` - a gate whose failure mode is "maybe allowed" is
 * not a gate. Every unexpected path therefore allows explicitly.
 */

const fs = require('fs')

const DESTRUCTIVE_TOOL = /(destroy|wipe[_-]?(device|disk)|format[_-]?(device|disk)|erase[_-]?device)/i
const CODEX_TOOL = /^codex(-reply)?$/

const hookIo = require('./lib/hook-io.cjs')

function readInput() {
  return hookIo.readStdin()
}

function allow() {
  process.stdout.write(JSON.stringify({ permission: 'allow' }))
  process.exit(0)
}

function deny(userMessage, agentMessage) {
  process.stdout.write(
    JSON.stringify({ permission: 'deny', user_message: userMessage, agent_message: agentMessage })
  )
  process.exit(0)
}

/** `tool_input` arrives as a JSON string, so a malformed one is a normal case. */
function parseParams(raw) {
  if (raw && typeof raw === 'object') return raw
  try {
    const parsed = JSON.parse(String(raw || '{}'))
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch (error) {
    return {}
  }
}

function main() {
  let payload
  try {
    payload = JSON.parse(readInput())
  } catch (error) {
    allow()
    return
  }

  const toolName = String(payload.tool_name || payload.toolName || '')
  if (toolName === '') {
    allow()
    return
  }

  if (DESTRUCTIVE_TOOL.test(toolName)) {
    deny(
      `Blocked the MCP tool "${toolName}". It asks to destroy a host resource, and no ` +
        'server configured for this repository does that.',
      `mcp-audit denied "${toolName}". Do not retry it and do not reach the same ` +
        'capability through a shell command. If the tool is genuinely needed, ask the human.'
    )
    return
  }

  if (CODEX_TOOL.test(toolName)) {
    const params = parseParams(payload.tool_input ?? payload.toolInput)
    const sandbox = String(params.sandbox || '')
    const approval = String(params['approval-policy'] || params.approval_policy || '')
    if (sandbox === 'danger-full-access' && approval === 'never') {
      deny(
        'Blocked a Codex call with sandbox "danger-full-access" and ' +
          'approval-policy "never". That is an unrestricted agent with no guardrails.',
        'mcp-audit denied this call. Re-issue it with sandbox "workspace-write" (or ' +
          '"read-only" for review), and let Codex ask for approval. For long work use ' +
          'scripts/codex-run.mjs, which refuses danger-full-access outright.'
      )
      return
    }
  }

  allow()
}

main()
