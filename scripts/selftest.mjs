#!/usr/bin/env node
/**
 * selftest: does the harness honour its own contracts?
 *
 * Why this exists
 * ---------------
 * `.cursor/rules/08-evidence-and-sensors.mdc` states the rule this script enforces: a
 * sensor that cannot fail is not a sensor. Every check below drives a real harness script
 * or hook on real input and asserts the documented behaviour, including the failure
 * behaviour - a permission hook that denies nothing, a runner that accepts a sandbox it
 * documents as refused, and a status sensor that cannot detect a missing file are all
 * worse than no check at all, because they produce confidence without evidence.
 *
 * The status-sensor checks run against a temporary tree with a deliberately injected
 * defect and assert the sensor reports it. That is the difference between "the sensor runs"
 * and "the sensor works", and only the second one is worth wiring into a gate.
 *
 * This is a repository-level gate, not a unit test of the product. It needs no database,
 * no network, no model and no Docker, and it is fast enough to run on every harness change.
 *
 * Usage: node scripts/selftest.mjs
 * Exit code 1 if any check fails.
 */

import { spawnSync } from 'node:child_process'
import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync
} from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import aliases from '../.cursor/mcp/mcp-aliases.cjs'
import { classifyFailure } from './lib/codex-signals.mjs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const HOOKS = join(ROOT, '.cursor', 'hooks')

let failures = 0
const scratch = []

function check(label, passed, detail = '') {
  console.log(`${(passed ? 'PASS' : 'FAIL').padEnd(6)} ${label}${detail ? ` - ${detail}` : ''}`)
  if (!passed) failures += 1
}

function section(title) {
  console.log(`\n## ${title}`)
}

/** A throwaway tree. Every one is removed at the end, including after a crash. */
function sandbox() {
  const directory = mkdtempSync(join(tmpdir(), 'velmor-selftest-'))
  scratch.push(directory)
  return directory
}

function write(root, relativePath, contents) {
  const full = join(root, relativePath)
  mkdirSync(dirname(full), { recursive: true })
  writeFileSync(full, contents)
  return full
}

function runScript(relativePath, args, options = {}) {
  return spawnSync(process.execPath, [join(ROOT, relativePath), ...args], {
    cwd: options.cwd || ROOT,
    input: options.input,
    encoding: 'utf8',
    timeout: 120_000,
    windowsHide: true,
    env: { ...process.env, ...(options.env || {}) }
  })
}

/**
 * Run a hook the way the runtime runs it.
 *
 * The BOM is not decoration. Cursor prefixes the hook payload with a UTF-8 byte-order mark on
 * Windows, `JSON.parse` rejects a leading U+FEFF, and every hook used to fall back to `{}` -
 * so every hook was inert in production while this suite passed, because the suite sent clean
 * JSON. Adding the BOM here is what makes the assertions below about the real payload instead
 * of an imagined one. Pass `{ bom: false }` to test the no-BOM path deliberately.
 */
function runHook(script, payload, env = {}, options = {}) {
  const body = typeof payload === 'string' ? payload : JSON.stringify(payload)
  const input = options.bom === false ? body : `\uFEFF${body}`
  return spawnSync(process.execPath, [join(HOOKS, script)], {
    cwd: ROOT,
    input,
    encoding: 'utf8',
    timeout: 30_000,
    windowsHide: true,
    env: { ...process.env, ...env }
  })
}

function output(result) {
  return `${result.stdout || ''}${result.stderr || ''}`
}

function joinNames(names) {
  return names.length > 0 ? names.join(', ') : '(none)'
}

function permission(result) {
  try {
    return JSON.parse(result.stdout || '{}').permission
  } catch (error) {
    return `(unparseable stdout: ${String(result.stdout).slice(0, 120)})`
  }
}

// ---------------------------------------------------------------------------
// Permission hooks
//
// Each of these decides something on every write or command in this repository. A hook
// that has silently stopped denying is the most expensive possible defect here, so both
// the deny path and the allow path are asserted. Asserting only the deny path would leave
// a hook that denies everything looking correct.
// ---------------------------------------------------------------------------

section('secret-guard')

const secretWrite = runHook('secret-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    path: 'packages/core/src/x.py',
    // Assembled at runtime on purpose. A literal key here makes this file match the pattern
    // the guard enforces, and the guard scans the content being written - so the fixture made
    // selftest.mjs itself uneditable. The payload the hook receives is still a complete
    // Stripe-shaped key, which is the thing under test.
    contents: `KEY = "sk_${'live'}_${'A'.repeat(24)}"\n`
  }
})
check(
  'denies a write containing a Stripe live key',
  permission(secretWrite) === 'deny',
  permission(secretWrite)
)

const cleanWrite = runHook('secret-guard.cjs', {
  tool_name: 'Write',
  tool_input: { path: 'packages/core/src/x.py', contents: 'KEY = os.environ["KEY"]\n' }
})
check('allows a clean write', permission(cleanWrite) === 'allow', permission(cleanWrite))

const readTool = runHook('secret-guard.cjs', {
  tool_name: 'Read',
  tool_input: { path: 'packages/core/src/x.py' }
})
check('ignores a non-write tool', permission(readTool) === 'allow', permission(readTool))

// A loopback DSN is the case this hook documents as exempt, and the case its own comment
// says .env.example needs. It was denied on every edit until the pattern was made to
// include the host, so both directions are asserted: the exemption fires, and a remote
// host holding a password is still refused. Assembled from parts for the reason given
// above - a literal DSN here would make this file itself match the guard.
const dsn = (scheme, userinfo, host, path) =>
  [scheme, '://', userinfo, '@', host, path].join('')

const localDsn = runHook('secret-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    path: 'packages/api/.env.example',
    contents: `DATABASE_URL=${dsn('postgresql+asyncpg', 'velmor:velmor', 'localhost:5432', '/velmor')}\n`
  }
})
check(
  'allows a loopback DSN - the exemption the hook documents',
  permission(localDsn) === 'allow',
  permission(localDsn)
)

const serviceDsn = runHook('secret-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    path: 'docker-compose.yml',
    contents: dsn('postgres', 'velmor:velmor', 'db:5432', '/velmor')
  }
})
check(
  'allows a compose service name',
  permission(serviceDsn) === 'allow',
  permission(serviceDsn)
)

const remoteDsn = runHook('secret-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    path: 'x.py',
    contents: dsn('postgres', 'user:pw', 'prod.example.com:5432', '/velmor')
  }
})
check(
  'denies a DSN with a password against a remote host',
  permission(remoteDsn) === 'deny',
  permission(remoteDsn)
)

const lookalikeDsn = runHook('secret-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    path: 'x.py',
    contents: dsn('postgres', 'user:pw', 'localhost.evil.com:5432', '/velmor')
  }
})
check(
  'denies a host that only starts with localhost',
  permission(lookalikeDsn) === 'deny',
  permission(lookalikeDsn)
)

// ---------------------------------------------------------------------------
// policy-guard: the rights surface and the harness itself require a human.
// ---------------------------------------------------------------------------

section('policy-guard')

const gateEdit = runHook('policy-guard.cjs', {
  tool_name: 'Write',
  tool_input: { path: 'packages/services/src/rights/publication_gate.py', contents: 'x = 1\n' }
})
check(
  'asks before an edit to the publication gate',
  permission(gateEdit) === 'ask',
  permission(gateEdit)
)

const ruleEdit = runHook('policy-guard.cjs', {
  tool_name: 'Write',
  tool_input: { path: '.cursor/rules/06-rights-engine.mdc', contents: 'x\n' }
})
check('asks before an edit to a rule', permission(ruleEdit) === 'ask', permission(ruleEdit))

const ordinaryEdit = runHook('policy-guard.cjs', {
  tool_name: 'Write',
  tool_input: { path: 'packages/services/src/domain/candidate.py', contents: 'x = 1\n' }
})
check('allows an ordinary edit', permission(ordinaryEdit) === 'allow', permission(ordinaryEdit))

// ---------------------------------------------------------------------------
// destructive-guard: irreversible commands, and nothing else.
// ---------------------------------------------------------------------------

section('destructive-guard')

for (const command of [
  'git reset --hard HEAD~1',
  'git push --force origin main',
  'docker compose down -v'
]) {
  const result = runHook('destructive-guard.cjs', { command })
  check(`denies: ${command}`, permission(result) === 'deny', permission(result))
}

for (const command of ['git status --short', 'git diff --stat', 'docker compose up -d']) {
  const result = runHook('destructive-guard.cjs', { command })
  check(`allows: ${command}`, permission(result) === 'allow', permission(result))
}

// ---------------------------------------------------------------------------
// mcp-audit: the one MCP policy a machine can decide.
// ---------------------------------------------------------------------------

section('mcp-audit')

const unsafeCodex = runHook('mcp-audit.cjs', {
  tool_name: 'codex',
  mcp_server_name: 'codex',
  tool_input: JSON.stringify({ sandbox: 'danger-full-access', 'approval-policy': 'never' })
})
check(
  'denies danger-full-access combined with approval-policy never',
  permission(unsafeCodex) === 'deny',
  permission(unsafeCodex)
)

const safeCodex = runHook('mcp-audit.cjs', {
  tool_name: 'codex',
  mcp_server_name: 'codex',
  tool_input: JSON.stringify({ sandbox: 'workspace-write', 'approval-policy': 'on-request' })
})
check('allows a guarded Codex call', permission(safeCodex) === 'allow', permission(safeCodex))

const replyUnsafe = runHook('mcp-audit.cjs', {
  tool_name: 'codex-reply',
  mcp_server_name: 'codex',
  tool_input: '{"sandbox":"danger-full-access","approval_policy":"never"}'
})
check(
  'detects the snake_case approval form on codex-reply',
  permission(replyUnsafe) === 'deny',
  permission(replyUnsafe)
)

const destructiveTool = runHook('mcp-audit.cjs', {
  tool_name: 'wipe_device',
  mcp_server_name: 'somewhere'
})
check('denies a destructive tool name', permission(destructiveTool) === 'deny', permission(destructiveTool))

const ordinaryTool = runHook('mcp-audit.cjs', {
  tool_name: 'query',
  mcp_server_name: 'postgres',
  tool_input: '{"sql":"select 1"}'
})
check('allows an ordinary MCP tool', permission(ordinaryTool) === 'allow', permission(ordinaryTool))

// A hook that throws is read as a hook failure, and failClosed then decides the outcome.
// With malformed input it must decide explicitly instead.
const malformed = runHook('mcp-audit.cjs', 'not json at all')
check(
  'decides explicitly on malformed input rather than crashing',
  malformed.status === 0 && permission(malformed) === 'allow',
  `exit=${malformed.status} ${permission(malformed)}`
)

// ---------------------------------------------------------------------------
// Lifecycle hooks
// ---------------------------------------------------------------------------

section('session-start')

const session = runHook('session-start.cjs', {
  workspace_roots: [ROOT],
  hook_event_name: 'sessionStart',
  conversation_id: 'selftest'
})
let sessionPayload = null
try {
  sessionPayload = JSON.parse(session.stdout || '{}')
} catch (error) {
  sessionPayload = null
}
check('exits 0', session.status === 0, `exit=${session.status}`)
check('returns additional_context', typeof sessionPayload?.additional_context === 'string')
check(
  'names the harness entry points',
  typeof sessionPayload?.additional_context === 'string' &&
    sessionPayload.additional_context.includes('/ship') &&
    sessionPayload.additional_context.includes('harness-status.mjs')
)
check('sets VELMOR_ROOT for the session', sessionPayload?.env?.VELMOR_ROOT === ROOT)

section('stop-gate')

const stopFirst = runHook('stop-gate.cjs', { status: 'completed', loop_count: 0 })
let stopPayload = null
try {
  stopPayload = JSON.parse(stopFirst.stdout || '{}')
} catch (error) {
  stopPayload = null
}
check('asks for evidence on the first completed stop', typeof stopPayload?.followup_message === 'string')

const stopSecond = runHook('stop-gate.cjs', { status: 'completed', loop_count: 1 })
check(
  'does not loop a second time',
  JSON.parse(stopSecond.stdout || '{}').followup_message === undefined
)

const stopAborted = runHook('stop-gate.cjs', { status: 'aborted', loop_count: 0 })
check(
  'stays silent when the session was aborted',
  JSON.parse(stopAborted.stdout || '{}').followup_message === undefined
)

const stopDisabled = runHook('stop-gate.cjs', { status: 'completed', loop_count: 0 }, { VELMOR_STOP_FOLLOWUP: '0' })
check(
  'honours VELMOR_STOP_FOLLOWUP=0',
  JSON.parse(stopDisabled.stdout || '{}').followup_message === undefined
)

section('after-file-edit')

const ledgerRoot = sandbox()
const edit = runHook('after-file-edit.cjs', {
  workspace_roots: [ledgerRoot],
  conversation_id: 'selftest',
  file_path: join(ledgerRoot, 'packages', 'core', 'src', 'x.py')
})
const ledgerDirectory = join(ledgerRoot, '.velmor', 'edit-ledger')
const ledgerEntries = existsSync(ledgerDirectory) ? readdirSync(ledgerDirectory) : []
const ledgerText = ledgerEntries
  .map((name) => readFileSync(join(ledgerDirectory, name), 'utf8'))
  .join('')
check('exits 0', edit.status === 0, `exit=${edit.status}`)
check('writes a dated ledger entry', ledgerEntries.some((name) => /^\d{4}-\d{2}-\d{2}\.log$/.test(name)), joinNames(ledgerEntries))
check(
  'records the edited path relative to the workspace root',
  ledgerText.includes('packages/core/src/x.py'),
  JSON.stringify(ledgerText.trim().split('\n').slice(-1)[0] || '')
)

const editDisabledRoot = sandbox()
runHook(
  'after-file-edit.cjs',
  { workspace_roots: [editDisabledRoot], file_path: join(editDisabledRoot, 'x.py') },
  { VELMOR_EDIT_LEDGER: '0' }
)
check('honours VELMOR_EDIT_LEDGER=0', !existsSync(join(editDisabledRoot, '.velmor')))

// ---------------------------------------------------------------------------
// The Codex runner's argument contract.
//
// Every case below is refused before a worker is started, so nothing is launched and no
// ledger record is created. That is the property being asserted as much as the message.
// ---------------------------------------------------------------------------

section('codex-run arguments')

const runner = 'scripts/codex-run.mjs'
const usage = runScript(runner, [])
check('prints usage with no command', usage.status === 0 && output(usage).includes('Codex worker runner'))

const promptFile = write(sandbox(), 'prompt.md', 'Reply with exactly: PONG\n')

const noPrompt = runScript(runner, ['run', '--id', 'selftest-no-prompt'])
check(
  'refuses run without --prompt-file',
  noPrompt.status === 1 && output(noPrompt).includes('--prompt-file is required'),
  output(noPrompt).trim().split('\n')[0]
)

const missingPrompt = runScript(runner, ['run', '--id', 'selftest-missing', '--prompt-file', 'harness/codex/prompts/nope.md'])
check(
  'refuses a prompt file that does not exist',
  missingPrompt.status === 1 && output(missingPrompt).includes('prompt file not found'),
  output(missingPrompt).trim().split('\n')[0]
)

const danger = runScript(runner, [
  'run', '--id', 'selftest-danger', '--prompt-file', promptFile, '--sandbox', 'danger-full-access'
])
check(
  'refuses --sandbox danger-full-access',
  danger.status === 1 && output(danger).includes('refusing --sandbox danger-full-access'),
  output(danger).trim().split('\n')[0]
)
check(
  'starts no worker when it refuses',
  !existsSync(join(ROOT, '.velmor', 'codex', 'selftest-danger.meta.json'))
)

const badEffort = runScript(runner, [
  'run', '--id', 'selftest-effort', '--prompt-file', promptFile, '--effort', 'turbo'
])
check(
  'refuses an unknown reasoning effort',
  badEffort.status === 1 && output(badEffort).includes('--effort must be one of'),
  output(badEffort).trim().split('\n')[0]
)

const badSandbox = runScript(runner, [
  'run', '--id', 'selftest-sandbox', '--prompt-file', promptFile, '--sandbox', 'root'
])
check(
  'refuses an unknown sandbox',
  badSandbox.status === 1 && output(badSandbox).includes('--sandbox must be one of'),
  output(badSandbox).trim().split('\n')[0]
)

const unknownWorker = runScript(runner, ['last', '--id', 'selftest-never-existed'])
check(
  'reports no final message for an unknown worker',
  output(unknownWorker).includes('(no final message yet)'),
  output(unknownWorker).trim()
)

// The operator guide and the runner must not drift apart: a documented command that the
// script does not accept is worse than an undocumented one.
const documented = readFileSync(join(ROOT, 'harness', 'codex-workers.md'), 'utf8')
for (const command of ['run', 'review', 'status', 'list', 'last', 'log', 'resume']) {
  check(
    `harness/codex-workers.md documents "${command}" and the runner offers it`,
    output(usage).includes(`  ${command}`) && documented.includes(`codex-run.mjs ${command}`),
    `usage=${output(usage).includes(`  ${command}`)} doc=${documented.includes(`codex-run.mjs ${command}`)}`
  )
}

// ---------------------------------------------------------------------------
// The Codex failure classifier.
//
// It selects a rung of the fallback ladder, so a false positive is expensive: an
// orchestrator switches writers for a failure that never happened. Every negative case
// below is a string that has already appeared in a real capture.
// ---------------------------------------------------------------------------

section('codex failure signals')

for (const [text, expected] of [
  ['usage limit reached, try again later', 'RATE_LIMITED'],
  ['Error: 429 Too Many Requests', 'RATE_LIMITED'],
  ['the context window was exceeded', 'CONTEXT_LIMIT'],
  ['stream error: 401 unauthorized', 'AUTH_ERROR'],
  ['request failed with status code 401', 'AUTH_ERROR'],
  ['Not logged in. Run `codex login` first.', 'AUTH_ERROR'],
  // The regression that made the classifier its own module: the ruff rule code F401 in a
  // file a worker had merely read was reported as an authentication failure.
  ['  "F401",', null],
  ['rate limit hit before the context window was exceeded', 'RATE_LIMITED'],
  ['DONE packages/core/src/x.py', null],
  ['', null]
]) {
  const actual = classifyFailure(text)
  check(
    `${expected === null ? 'no signal' : expected} <- ${JSON.stringify(text.slice(0, 48))}`,
    actual === expected,
    actual === expected ? '' : `got ${actual}`
  )
}

// ---------------------------------------------------------------------------
// codex-gate: the Codex-first requirement, which had no enforcement at all until now.
//
// The requirement is that product code is written by a Codex worker. Both directions matter:
// a gate that blocks legitimate harness work is unusable, and a gate that allows product code
// is the defect this exists to fix. The window is forced to 1 minute so the allow/deny pair
// does not depend on how long ago a real worker happened to run.
// ---------------------------------------------------------------------------

section('codex-gate')

const gateRoot = sandbox()
write(gateRoot, '.velmor/session/epoch', `${new Date().toISOString()}\n`)
const gate = (payload, env = {}) =>
  runHook('codex-gate.cjs', { workspace_roots: [gateRoot], ...payload }, {
    VELMOR_CODEX_WINDOW_MIN: '1',
    ...env
  })

const productWrite = (path) => ({ tool_name: 'Write', tool_input: { path } })

check(
  'denies product code with no worker behind it',
  permission(gate(productWrite('packages/core/src/x.py'))) === 'deny',
  permission(gate(productWrite('packages/core/src/x.py')))
)
check(
  'denies velmor/ and storefront/ too',
  permission(gate(productWrite('velmor/cli.py'))) === 'deny' &&
    permission(gate(productWrite('storefront/src/app/page.tsx'))) === 'deny'
)
check(
  'never gates the verdict path',
  permission(gate(productWrite('packages/services/src/rights/publication_gate.py'))) === 'allow' &&
    permission(gate(productWrite('packages/services/src/screening/prohibited_screen.py'))) === 'allow'
)
check(
  'never gates the harness itself',
  permission(gate(productWrite('.cursor/hooks/codex-gate.cjs'))) === 'allow' &&
    permission(gate(productWrite('harness/README.md'))) === 'allow' &&
    permission(gate(productWrite('scripts/selftest.mjs'))) === 'allow' &&
    permission(gate(productWrite('AGENTS.md'))) === 'allow' &&
    permission(gate(productWrite('openspec/config.yaml'))) === 'allow'
)
check(
  'ignores a non-write tool',
  permission(gate({ tool_name: 'Read', tool_input: { path: 'packages/core/src/x.py' } })) === 'allow'
)
check(
  'decides explicitly on malformed input',
  (() => {
    const result = runHook('codex-gate.cjs', 'not json', { VELMOR_CODEX_WINDOW_MIN: '1' })
    return result.status === 0 && permission(result) === 'allow'
  })()
)
check(
  'honours VELMOR_CODEX_GATE=off',
  permission(gate(productWrite('packages/core/src/x.py'), { VELMOR_CODEX_GATE: 'off' })) === 'allow'
)

// The allow half: a worker recorded in the ledger must satisfy the gate. Without this the
// check above would pass for a hook that denies unconditionally.
const gateLedger = sandbox()
write(gateLedger, '.velmor/session/epoch', `${new Date().toISOString()}\n`)
write(
  gateLedger,
  '.velmor/codex/task-1.meta.json',
  `${JSON.stringify({ id: 'task-1', startedAt: new Date().toISOString() })}\n`
)
const withWorker = runHook(
  'codex-gate.cjs',
  { tool_name: 'Write', workspace_roots: [gateLedger], tool_input: { path: 'packages/core/src/x.py' } },
  { VELMOR_CODEX_WINDOW_MIN: '1' }
)
check(
  'allows product code once a worker is recorded in this session',
  permission(withWorker) === 'allow',
  permission(withWorker)
)

// And a worker from before this session must not count, or the requirement degrades into
// "Codex ran once, ever".
const staleRoot = sandbox()
write(staleRoot, '.velmor/session/epoch', `${new Date().toISOString()}\n`)
write(
  staleRoot,
  '.velmor/codex/old.meta.json',
  `${JSON.stringify({ id: 'old', startedAt: new Date(Date.now() - 86_400_000).toISOString() })}\n`
)
write(staleRoot, '.velmor/codex/old.exit.json', '{}\n')
const staleWorker = runHook(
  'codex-gate.cjs',
  { tool_name: 'Write', workspace_roots: [staleRoot], tool_input: { path: 'packages/core/src/x.py' } },
  { VELMOR_CODEX_WINDOW_MIN: '1' }
)
check(
  'a worker from before this session does not satisfy the gate',
  permission(staleWorker) === 'deny',
  permission(staleWorker)
)

// ---------------------------------------------------------------------------
// The MCP launcher.
// ---------------------------------------------------------------------------

section('run-mcp')

const noAlias = runScript('.cursor/mcp/run-mcp.cjs', [])
check(
  'refuses to start without an alias',
  noAlias.status === 1 && output(noAlias).includes('usage: node run-mcp.cjs'),
  output(noAlias).trim().split('\n')[0]
)

// Read the alias table itself rather than the text of the file that defines it. Grepping
// the source would report a false failure for a quoted key, and would accept a name that
// appears in a comment.
const config = JSON.parse(readFileSync(join(ROOT, '.cursor', 'mcp.json'), 'utf8'))
let aliasMismatch = 0
for (const [name, server] of Object.entries(config.mcpServers || {})) {
  const args = Array.isArray(server.args) ? server.args : []
  if (!String(args[0] || '').endsWith('run-mcp.cjs')) continue
  if (!Object.prototype.hasOwnProperty.call(aliases, args[1])) {
    aliasMismatch += 1
    console.log(`       ${name} uses alias "${args[1]}", absent from mcp-aliases.cjs`)
  }
}
check('every run-mcp alias in mcp.json exists in the alias table', aliasMismatch === 0)

// ---------------------------------------------------------------------------
// The status sensor, driven against an injected defect.
//
// This is the check that gives the others their meaning: it proves harness-status.mjs can
// report FAIL, and that it names the particular thing that is wrong rather than failing
// generically.
// ---------------------------------------------------------------------------

section('harness-status detects injected defects')

const incomplete = sandbox()
const incompleteRun = runScript('scripts/harness-status.mjs', ['--root', incomplete])
check(
  'reports NOT READY for an empty tree',
  incompleteRun.status === 1 && output(incompleteRun).includes('VERDICT: NOT READY')
)
check(
  'names a missing required surface',
  output(incompleteRun).includes('FAIL     AGENTS.md'),
  'expected the AGENTS.md line'
)

const drifted = sandbox()
write(drifted, 'AGENTS.md', '# stub\n')
write(drifted, '.gitignore', '.env\n')
write(drifted, '.cursor/agents/planner.md', '---\nname: planner\n---\n')
write(
  drifted,
  '.cursor/mcp.json',
  `${JSON.stringify(
    {
      mcpServers: {
        'a-server': { command: 'node', args: ['${workspaceFolder}/.cursor/mcp/run-mcp.cjs', 'no-such-alias'] },
        context7: { command: 'node', args: ['${workspaceFolder}/.cursor/mcp/run-mcp.cjs', 'context7'] },
        playwright: { command: 'node', args: ['${workspaceFolder}/.cursor/mcp/run-mcp.cjs', 'playwright'] },
        codex: { command: 'node', args: ['${workspaceFolder}/.cursor/mcp/codex-launcher.cjs', 'mcp-server'] },
        postgres: { command: 'uvx', args: ['postgres-mcp'] }
      }
    },
    null,
    2
  )}\n`
)
write(
  drifted,
  '.cursor/hooks.json',
  `${JSON.stringify(
    { version: 1, hooks: { preToolUse: [{ command: 'node .cursor/hooks/not-there.cjs' }] } },
    null,
    2
  )}\n`
)
const driftedRun = runScript('scripts/harness-status.mjs', ['--root', drifted])
const driftedOutput = output(driftedRun)
check(
  'names a subagent that is not mirrored',
  driftedOutput.includes('missing from .claude/agents, .codex/agents'),
  'expected a mirror-parity FAIL'
)
check(
  'names an MCP alias that does not resolve',
  driftedOutput.includes('alias "no-such-alias" resolves in .cursor/mcp/mcp-aliases.cjs'),
  'expected an alias FAIL'
)
check(
  'names a hook script that does not exist',
  driftedOutput.includes('.cursor/hooks/not-there.cjs'),
  'expected a hook-wiring FAIL'
)
check(
  'detects .velmor/ missing from .gitignore',
  driftedOutput.includes('.gitignore ignores .velmor/'),
  'expected the gitignore FAIL'
)

// A `config.yaml` OpenSpec cannot read is the worst kind of harness failure: it warns,
// ignores the file, and still reports every change as valid, so the project contract silently
// disappears from all future work. The sensor has to scan the output because the exit code
// stays 0. The injected text is a plain multi-line scalar whose continuation line contains
// `key: ` - the exact shape that produced "Implicit keys need to be on a single line".
const brokenSpec = sandbox()
cpSync(join(ROOT, 'openspec'), join(brokenSpec, 'openspec'), { recursive: true })
write(
  brokenSpec,
  'openspec/config.yaml',
  'schema: spec-driven\nrules:\n  proposal:\n    - A plain scalar, first line\n      output: a colon here breaks the parse\n'
)
const brokenRun = runScript('scripts/harness-status.mjs', ['--root', brokenSpec], { cwd: brokenSpec })
check(
  'detects an openspec/config.yaml that does not parse',
  output(brokenRun).includes('OpenSpec is ignoring part of openspec/config.yaml'),
  `expected the config-parse FAIL; got: ${output(brokenRun)
    .split(/\r?\n/)
    .filter((line) => /openspec validate|ignoring|FAIL.*config/i.test(line))
    .slice(0, 2)
    .join(' | ')}`
)

section('setup-mcp')

const setup = runScript('scripts/setup-mcp.mjs', [])
check(
  'resolves every declared server',
  setup.status === 0 && output(setup).includes('every launcher resolves'),
  output(setup).trim().split('\n').slice(-1)[0]
)

section('sync-agents')

const agentsCheck = runScript('scripts/sync-agents.mjs', ['--check'])
check(
  'the subagent mirrors are in sync with .cursor/agents/',
  agentsCheck.status === 0 && output(agentsCheck).includes('in sync'),
  output(agentsCheck).trim().split('\n').slice(-1)[0]
)

// ---------------------------------------------------------------------------

for (const directory of scratch) {
  rmSync(directory, { recursive: true, force: true })
}

console.log(`\nVERDICT: ${failures === 0 ? 'PASS' : `FAIL (${failures} checks)`}`)
process.exitCode = failures === 0 ? 0 : 1
