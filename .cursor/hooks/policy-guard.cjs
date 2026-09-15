// policy-guard: a human must approve edits to the surfaces that decide what the
// company may legally sell, and to the agent harness itself.
//
// Why this exists rather than a comment in a rule file:
//
//   `license_grants.py` is the table that says which licences permit which
//   actions, and `publication_gate.py` is the function that decides whether a
//   good may be listed. A silent edit to either one changes the company's legal
//   exposure, and the edit is indistinguishable from a refactor in a diff. The
//   harness files (rules, hooks, AGENTS.md) are the agent's own operating
//   instructions: an agent that can quietly relax its own rules is not governed
//   by them.
//
// This returns "ask", never "deny". The edit may well be exactly right - it
// still requires a named human to say so, once, per edit.
//
// Contract: tool-call JSON on stdin, permission JSON on stdout, exit 0.

const fs = require('fs')

// Files whose content changes what Velmor is allowed to sell.
const POLICY_FILES = [
  'packages/services/src/rights/license_grants.py',
  'packages/services/src/rights/license_matrix.py',
  'packages/services/src/rights/publication_gate.py',
  'packages/services/src/rights/rights_resolver.py',
  'packages/services/src/rights/engine.py',
  'packages/services/src/screening/prohibited_screen.py'
]

// Files that govern the agents themselves.
const HARNESS_FILES = [
  '.cursor/rules/',
  '.cursor/hooks.json',
  '.cursor/hooks/',
  '.cursor/commands/',
  '.cursor/mcp.json',
  'AGENTS.md',
  'CLAUDE.md',
  'openspec/config.yaml'
]

function targetPath(toolInput) {
  return toolInput.path || toolInput.file_path || toolInput.filePath || toolInput.target_file || ''
}

function normalise(filePath) {
  return String(filePath).replace(/\\/g, '/').replace(/^\.\//, '')
}

function matches(candidate, entry) {
  if (entry.endsWith('/')) return candidate === entry.slice(0, -1) || candidate.startsWith(entry)
  return candidate === entry
}

function readInput() {
  try {
    return fs.readFileSync(0, 'utf8')
  } catch (error) {
    return ''
  }
}

function allow() {
  process.stdout.write(JSON.stringify({ permission: 'allow' }))
  process.exit(0)
}

function ask(reason, agentMessage) {
  process.stdout.write(
    JSON.stringify({
      permission: 'ask',
      user_message: reason,
      agent_message: agentMessage
    })
  )
  process.exit(0)
}

function main() {
  let payload
  try {
    payload = JSON.parse(readInput())
  } catch (error) {
    allow()
    return
  }

  const toolName = payload.tool_name || payload.toolName || ''
  if (!/^(Write|StrReplace|EditNotebook)$/.test(toolName)) {
    allow()
    return
  }

  const candidate = normalise(targetPath(payload.tool_input || payload.toolInput || {}))
  if (candidate === '') {
    allow()
    return
  }

  if (POLICY_FILES.some((entry) => matches(candidate, entry))) {
    ask(
      'This file decides what Velmor may publish (' +
        candidate +
        '). A change here is a policy decision, so it needs your explicit approval. ' +
        'Confirm the licence reasoning before allowing it.',
      'policy-guard requires human approval for edits to the rights policy surface.'
    )
    return
  }

  if (HARNESS_FILES.some((entry) => matches(candidate, entry))) {
    ask(
      'This file configures the agent harness itself (' +
        candidate +
        '). Allowing an agent to edit its own rules or gates removes the constraint, ' +
        'so the change needs your approval.',
      'policy-guard requires human approval for edits to the harness configuration.'
    )
    return
  }

  allow()
}

main()
