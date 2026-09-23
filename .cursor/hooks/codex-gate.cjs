#!/usr/bin/env node
/**
 * codex-gate - product code is written by a Codex worker, not by the orchestrator.
 *
 * Why this exists
 * ---------------
 * The project rule is that Codex owns implementation and Cursor verifies, falling back to
 * Cursor only when Codex is blocked. That rule lived in prose, and prose had no teeth:
 * `/ship` dispatched a Cursor implementer subagent, Codex was one optional row in a table,
 * and an agent that simply did the work itself produced no failure anywhere. A rule that
 * cannot fail is not a rule - the same defect this repository already wrote a lesson about.
 *
 * This hook is the enforcement. It intercepts a write to product code and refuses it unless
 * a Codex worker has actually run in this session. The evidence is the worker ledger that
 * `scripts/codex-run.mjs` writes, so "there was a worker" means a session was started and
 * recorded, not that someone asserted one was.
 *
 * What is gated, and what is not
 * ------------------------------
 * Gated (must come from a Codex worker):
 *   packages/** and velmor/** and storefront/**
 *
 * Never gated (the orchestrator's own job, by design):
 *   .cursor/**, .claude/**, .codex/**, harness/**, scripts/**, docs/**, openspec/**,
 *   and every root file - rules, hooks, commands, agents, MCP, specs and harness docs.
 *   Handing the harness to Codex would mean the author of a constraint is the author of
 *   its enforcement.
 *
 * Deliberately exceptioned inside the gated paths:
 *   packages/services/src/rights/** and packages/services/src/screening/** - the verdict
 *   path. `AGENTS.md` forbids a model-run agent from touching what the company may legally
 *   sell, and `policy-guard.cjs` already requires a human to approve an edit there. Sending
 *   these to Codex would be a rights-contract violation, so the gate stands aside for them.
 *
 * Escape hatch
 * ------------
 * `VELMOR_CODEX_GATE=off` allows everything for one shell/session. It exists because a
 * genuine exception must have a documented door: a one-line typo fix, a rights edit, or a
 * machine where Codex is unavailable. Use it consciously, and say so in the handoff.
 *
 * Failure mode
 * ------------
 * `failClosed: false` in hooks.json. This is a workflow gate, not a security boundary: if
 * Node itself is broken, bricking every product write would leave nothing repairable. The
 * code below is nonetheless written to reach an explicit decision on every path, and any
 * path that can read the ledger at all denies when no worker is found. Malformed hook input
 * allows, because the hook cannot even tell what is being attempted.
 *
 * Contract: tool-call JSON on stdin, permission JSON on stdout, exit 0.
 */

const fs = require('fs')
const path = require('path')

// Product code: implementation that a Codex worker owns.
const PRODUCT_ROOTS = ['packages/', 'velmor/', 'storefront/']

// The verdict path. Never delegated, so never gated.
const NEVER_DELEGATED = ['packages/services/src/rights/', 'packages/services/src/screening/']

const WRITE_TOOLS = /^(Write|StrReplace|EditNotebook)$/
const DISABLED = /^(0|off|false)$/i

/**
 * A worker older than this does not count, so the requirement is "a Codex worker ran for
 * this work", not "Codex ran at some point in the repository's history". A worker that has
 * not exited yet always counts, however long it has been running.
 */
const WINDOW_MINUTES = Number(process.env.VELMOR_CODEX_WINDOW_MIN || 180)

const hookIo = require('./lib/hook-io.cjs')

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

// `normalise` and `workspaceRelative` moved to `lib/hook-io.cjs`. Three hooks resolve a
// write target the same way, and one definition imported by all three is what keeps them
// from drifting apart.

function targetPath(toolInput) {
  return toolInput.path || toolInput.file_path || toolInput.filePath || toolInput.target_file || ''
}

/**
 * Whether the process recorded in a worker's meta file is still alive.
 *
 * A record with no exit file is treated as a worker that is still running, which is what lets a
 * worker started a moment ago count. That is only sound while the worker is actually alive: a
 * runner killed by an operator writes no exit record, so the record stayed eligible forever and
 * the gate was silently open from then on. Measured on this repository: two killed Codex reviews
 * left exactly that state. `pid` is the meta file's own record of the runner.
 *
 * `null` means the record carries no pid, and the caller falls back to the time window.
 *
 * `process.kill(pid, 0)` is the only existence probe Node offers and it throws when the target
 * is gone, so a catch here is the contract rather than a swallowed failure: `EPERM` means the
 * process exists but belongs to another user, and every other code means it does not exist.
 */
function processAlive(pid) {
  if (pid === null) return true
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    return error.code === 'EPERM'
  }
}

/** Workers recorded by scripts/codex-run.mjs, newest first. */
function codexWorkers(root) {
  const ledger = path.join(root, '.velmor', 'codex')
  let names
  try {
    names = fs.readdirSync(ledger).filter((name) => name.endsWith('.meta.json'))
  } catch (error) {
    return []
  }

  const workers = []
  for (const name of names) {
    const file = path.join(ledger, name)
    let meta
    try {
      meta = JSON.parse(fs.readFileSync(file, 'utf8'))
    } catch (error) {
      // An unreadable record is not a worker. Reported on stderr so a corrupt ledger is
      // visible rather than silently permissive.
      console.error(`codex-gate: cannot read ${file}`)
      continue
    }
    workers.push({
      id: meta.id || name.replace(/\.meta\.json$/, ''),
      startedAt: Date.parse(meta.startedAt || '') || 0,
      pid: Number.isInteger(meta.pid) ? meta.pid : null,
      running: !fs.existsSync(path.join(ledger, `${meta.id || ''}.exit.json`))
    })
  }
  return workers.sort((left, right) => right.startedAt - left.startedAt)
}

function sessionEpoch(root) {
  try {
    const text = fs.readFileSync(path.join(root, '.velmor', 'session', 'epoch'), 'utf8').trim()
    return Date.parse(text) || 0
  } catch (error) {
    return 0
  }
}

function main() {
  const payload = hookIo.readPayload()

  const toolName = String(payload.tool_name || payload.toolName || '')
  if (!WRITE_TOOLS.test(toolName)) {
    allow()
    return
  }

  const root = hookIo.workspaceRoot(payload)
  const candidate = hookIo.workspaceRelative(
    targetPath(payload.tool_input || payload.toolInput || {}),
    root
  )
  if (candidate === '') {
    allow()
    return
  }
  if (!PRODUCT_ROOTS.some((root) => candidate.startsWith(root))) {
    allow()
    return
  }
  if (NEVER_DELEGATED.some((root) => candidate.startsWith(root))) {
    allow()
    return
  }
  if (DISABLED.test(process.env.VELMOR_CODEX_GATE || '')) {
    allow()
    return
  }

  const workers = codexWorkers(root)
  const epoch = sessionEpoch(root)
  // With no session marker, fall back to the time window rather than allowing: a deleted
  // marker must not be a way to switch the requirement off.
  const floor = epoch > 0 ? epoch : Date.now() - WINDOW_MINUTES * 60_000
  // A record with no exit file counts only while its worker is actually alive; a killed runner
  // leaves no exit file, and treating that record as a worker kept the gate open indefinitely.
  // A record that carries no pid falls back to the window, as it always did.
  const eligible = workers.filter(
    (worker) => (worker.running && processAlive(worker.pid)) || worker.startedAt >= floor
  )

  if (eligible.length > 0) {
    allow()
    return
  }

  const recent = workers.length > 0
    ? `The newest worker on record is ${workers[0].id}, started ${new Date(workers[0].startedAt).toISOString()}, which is outside this session.`
    : 'No Codex worker has ever run in this repository.'

  deny(
    `Blocked a write to ${candidate} because no Codex worker has run in this session.\n\n` +
      'Implementation is Codex\'s job here, and Cursor verifies it. Start a worker first:\n\n' +
      '  node scripts/codex-run.mjs run --id <id> \\\n' +
      '    --prompt-file harness/codex/prompts/<prompt>.md --sandbox workspace-write\n\n' +
      `${recent}\n\n` +
      'If this edit genuinely belongs to Cursor - a one-line fix, or the rights verdict path - ' +
      'set VELMOR_CODEX_GATE=off for this session and say so in the handoff.',
    'codex-gate denied this write. Product code is implemented by a Codex worker, because a ' +
      'second model family is the point: delegate via scripts/codex-run.mjs and verify the ' +
      'diff afterwards. Do not disable the gate to avoid delegating; disable it only for a ' +
      'documented exception such as the rights verdict path.'
  )
}

main()
