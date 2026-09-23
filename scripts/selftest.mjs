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
 * Run a Python snippet through the project environment.
 *
 * Only the publication-guard check below needs this. It is a snippet rather than a file
 * because a fixture committed under `packages/` becomes product code: it would be gated
 * by the hooks, counted by the suite and reviewed as behaviour, when what it is is a
 * probe of one refusal. `python -` reads the program from stdin and puts the working
 * directory on `sys.path`, so `packages` and `velmor` resolve without a wrapper.
 */
function runPython(source) {
  return spawnSync('uv', ['run', 'python', '-'], {
    cwd: ROOT,
    input: source,
    encoding: 'utf8',
    timeout: 120_000,
    windowsHide: true
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

// The checks above send a repository-relative `path`. The runtime sends an **absolute**
// `file_path` - measured as `d:\Python\Velmor\packages\...` - so on its own the block above
// certifies a payload the runtime never sends, which is how this hook went inert in
// production while the suite stayed green. Both directions are asserted here: the policy
// surface must be caught at an absolute path, and an ordinary file must still be allowed so
// the resolution cannot turn into a blanket ask.
const urlLikeRoot = '/' + ROOT.replace(/\\/g, '/')

const absoluteGateEdit = runHook('policy-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    file_path: join(ROOT, 'packages', 'services', 'src', 'rights', 'publication_gate.py'),
    contents: 'x = 1\n'
  },
  workspace_roots: [urlLikeRoot]
})
check(
  'asks before an edit to the publication gate - the absolute path the runtime sends',
  permission(absoluteGateEdit) === 'ask',
  permission(absoluteGateEdit)
)

const absoluteRuleEdit = runHook('policy-guard.cjs', {
  tool_name: 'Write',
  tool_input: { file_path: join(ROOT, '.cursor', 'rules', '06-rights-engine.mdc'), contents: 'x\n' },
  workspace_roots: [urlLikeRoot]
})
check(
  'asks before an edit to a rule - the absolute path the runtime sends',
  permission(absoluteRuleEdit) === 'ask',
  permission(absoluteRuleEdit)
)

const absoluteOrdinaryEdit = runHook('policy-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    file_path: join(ROOT, 'packages', 'services', 'src', 'domain', 'candidate.py'),
    contents: 'x = 1\n'
  },
  workspace_roots: [urlLikeRoot]
})
check(
  'allows an ordinary edit at an absolute path',
  permission(absoluteOrdinaryEdit) === 'allow',
  permission(absoluteOrdinaryEdit)
)

// ---------------------------------------------------------------------------
// ui-guard: buyer-visible copy and a chosen language must not live in a component.
//
// This hook had no check at all until now, so nothing ever observed whether it fires. Its
// payload is the same absolute-path shape as the two guards above, and the literal below is
// the exact defect it exists to catch: a Cyrillic string written into a component instead of
// into `storefront/src/lib/i18n/*.json`.
// ---------------------------------------------------------------------------

section('ui-guard')

const cyrillicComponent = runHook('ui-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    file_path: join(ROOT, 'storefront', 'src', 'app', 'page.tsx'),
    contents: 'export default () => <button>Добавить в корзину</button>\n'
  },
  workspace_roots: [urlLikeRoot]
})
check(
  'denies Cyrillic copy in a component - the absolute path the runtime sends',
  permission(cyrillicComponent) === 'deny',
  permission(cyrillicComponent)
)

const hardcodedLanguage = runHook('ui-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    file_path: join(ROOT, 'storefront', 'src', 'app', 'layout.tsx'),
    contents: 'export default () => <html lang="be"><body /></html>\n'
  },
  workspace_roots: [urlLikeRoot]
})
check(
  'denies a literal language in lang=',
  permission(hardcodedLanguage) === 'deny',
  permission(hardcodedLanguage)
)

const cleanComponent = runHook('ui-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    file_path: join(ROOT, 'storefront', 'src', 'app', 'page.tsx'),
    contents: 'export default () => <button>{t("addToCart")}</button>\n'
  },
  workspace_roots: [urlLikeRoot]
})
check(
  'allows a component that reads its copy from the dictionary',
  permission(cleanComponent) === 'allow',
  permission(cleanComponent)
)

const localeDictionary = runHook('ui-guard.cjs', {
  tool_name: 'Write',
  tool_input: {
    file_path: join(ROOT, 'storefront', 'src', 'lib', 'i18n', 'ru.json'),
    contents: '{ "addToCart": "Добавить в корзину" }\n'
  },
  workspace_roots: [urlLikeRoot]
})
check(
  'allows the locale dictionary, which is the sanctioned home for copy',
  permission(localeDictionary) === 'allow',
  permission(localeDictionary)
)

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
// codex-run ledger: a killed worker must not be reported as `running`.
//
// A worker killed by an operator, a closed terminal or a machine restart never writes an exit
// record, so `status` fell back to the launch-time word `running` and kept saying it. Measured:
// two workers still read `running` after 155 and 140 minutes while `process.kill(pid, 0)` said
// the pids were gone. A reader deciding whether to wait or to re-dispatch waits forever on that
// word, so the false reading is worse than a failure would have been.
//
// The injection is the defect itself: a ledger entry carrying a pid no live process can hold,
// and no exit record. It must read LOST, and it must not read `running`.
// ---------------------------------------------------------------------------

section('codex-run ledger liveness')

const lostFixture = join(ROOT, '.velmor', 'codex', 'selftest-lost-worker.meta.json')
mkdirSync(dirname(lostFixture), { recursive: true })
// A pid beyond the addressable range, so the probe is deterministic rather than a race. A real
// short-lived child could be reused by the OS between spawning it and asking about it, which
// would make this check flaky in the one direction that matters.
writeFileSync(
  lostFixture,
  JSON.stringify({
    id: 'selftest-lost-worker',
    kind: 'run',
    label: 'selftest fixture',
    status: 'running',
    pid: 2147483000,
    startedAt: '2020-01-01T00:00:00.000Z'
  })
)
scratch.push(lostFixture)

const lostStatus = runScript('scripts/codex-run.mjs', ['status', '--id', 'selftest-lost-worker'])
const lostLine = output(lostStatus).trim().split('\n').slice(-1)[0]
check(
  'a worker whose process is gone is reported LOST, never running',
  lostLine.startsWith('LOST') && !lostLine.includes('running'),
  lostLine || '(no output)'
)

// ---------------------------------------------------------------------------
// Harness scripts must be parseable.
//
// `scripts/selftest.mjs` carried a UTF-8 BOM, which `node --check` rejects at the shebang
// (`SyntaxError: Invalid or unexpected token` on line 1) while `node <file>` runs the same file
// happily. The one script whose job is proving that the harness's own sensors work therefore could
// not itself be syntax-checked, and no gate noticed. A BOM is invisible in every editor and in
// every diff, which is why this is a sensor and not a note.
// ---------------------------------------------------------------------------

section('harness scripts are parseable')

const BOM_BYTES = [0xef, 0xbb, 0xbf]
const scriptsWithBom = []

function scanForBom(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === 'node_modules') continue
    const full = join(directory, entry.name)
    if (entry.isDirectory()) {
      scanForBom(full)
      continue
    }
    if (!/\.(mjs|cjs|js)$/.test(entry.name)) continue
    const head = readFileSync(full).subarray(0, 3)
    if (head[0] === BOM_BYTES[0] && head[1] === BOM_BYTES[1] && head[2] === BOM_BYTES[2]) {
      scriptsWithBom.push(full.slice(ROOT.length + 1).replace(/\\/g, '/'))
    }
  }
}

for (const directory of [join(ROOT, 'scripts'), join(ROOT, '.cursor', 'hooks')]) {
  scanForBom(directory)
}

check(
  'no harness script carries a UTF-8 BOM (it makes `node --check` reject the shebang)',
  scriptsWithBom.length === 0,
  scriptsWithBom.join(', ')
)

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

// The payload the runtime actually sends for a write carries an **absolute** path. Measured on
// this machine: `tool_input.file_path` = `d:\Python\Velmor\packages\...`, not `packages/...`.
// Every check above sends the relative form, which is the form the gate used to match - so the
// suite certified a payload the runtime never sends, and the gate allowed every real product
// write before it read the worker ledger. Both directions are asserted: the absolute
// in-workspace path must be judged exactly like the relative one, and an absolute path outside
// the workspace must not be pulled into the gated roots by the resolution itself.
const absoluteWrite = (filePath) => ({ tool_name: 'Write', tool_input: { file_path: filePath } })
const absoluteProduct = join(gateRoot, 'packages', 'core', 'src', 'x.py')

check(
  'denies an absolute path to product code - the payload the runtime sends',
  permission(gate(absoluteWrite(absoluteProduct))) === 'deny',
  permission(gate(absoluteWrite(absoluteProduct)))
)
check(
  'allows an absolute path outside the workspace',
  permission(gate(absoluteWrite(join(sandbox(), 'packages', 'core', 'src', 'x.py')))) === 'allow',
  permission(gate(absoluteWrite(join(sandbox(), 'packages', 'core', 'src', 'x.py'))))
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

// A record with no exit file is treated as a worker that is still running. That is right for a
// worker started a moment ago, and it is what makes the gate usable. It becomes wrong across a
// session boundary: killing a runner (an operator's `Stop-Process`, a killed background job)
// writes no exit record, so a worker from a *previous* session stayed `running` forever, and
// `running` bypassed the session window that exists precisely to stop "Codex ran once, ever".
// Measured on this repository: two killed Codex reviews left exactly that state. The record's own
// `pid` is the evidence, and the worker below is deliberately dated before the session so the
// liveness clause is what decides, not the window.
const killedPid = spawnSync(process.execPath, ['-e', '0']).pid
const yesterday = new Date(Date.now() - 86_400_000).toISOString()

const killedRoot = sandbox()
write(killedRoot, '.velmor/session/epoch', `${new Date().toISOString()}\n`)
write(
  killedRoot,
  '.velmor/codex/killed.meta.json',
  `${JSON.stringify({ id: 'killed', startedAt: yesterday, pid: killedPid })}\n`
)
const killedWorker = runHook(
  'codex-gate.cjs',
  { tool_name: 'Write', workspace_roots: [killedRoot], tool_input: { path: 'packages/core/src/x.py' } },
  { VELMOR_CODEX_WINDOW_MIN: '1' }
)
check(
  'denies a worker from a previous session that was killed, not merely a stale timestamp',
  permission(killedWorker) === 'deny',
  permission(killedWorker)
)

const liveRoot = sandbox()
write(liveRoot, '.velmor/session/epoch', `${new Date().toISOString()}\n`)
write(
  liveRoot,
  '.velmor/codex/live.meta.json',
  `${JSON.stringify({ id: 'live', startedAt: yesterday, pid: process.pid })}\n`
)
const liveWorker = runHook(
  'codex-gate.cjs',
  { tool_name: 'Write', workspace_roots: [liveRoot], tool_input: { path: 'packages/core/src/x.py' } },
  { VELMOR_CODEX_WINDOW_MIN: '1' }
)
check(
  'allows a worker that is still running, however long it has run',
  permission(liveWorker) === 'allow',
  permission(liveWorker)
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
// The publication guard: the bridge must not trust a caller's assertion.
//
// `.cursor/commands/rights-verify.md` invariant 5 says the bridge raises `RightsDeniedError`
// for a caller presenting a decision the gate contradicts. Nothing observed that until now,
// and this is the check that does: it applies the real bridge to a decision asserting
// `publishable` over a record the gate refuses - a model reading plus the identity match
// derived from it, which is the cheapest record the gate turns away.
//
// The probe deliberately lets the error propagate. The `print` after `apply` is the failure
// path, so a nonzero exit whose traceback names `RightsDeniedError` is the passing case, and
// nothing catches the error to observe it: this change adds a raise, not a catch. The fixture
// is assembled here rather than committed under `packages/`, where it would be product code
// subject to the hooks and to a different suite; the guard's own regression case lives in
// `test_publication.py`.
// ---------------------------------------------------------------------------

section('publication guard')

const guardProbe = runPython(`
import asyncio
from datetime import UTC, datetime

from packages.services.src.commerce.publication import PublicationBridge
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.rights import EvidenceKind
from packages.services.src.rights.license_grants import DefaultLicenseGrants
from packages.services.src.rights.license_matrix import LicenseMatrix
from packages.services.src.rights.publication_gate import PublicationGate
from packages.services.tests.conftest import build_candidate, build_record, build_spec


class EmptyCatalogue:
    """The store port. A record the gate refuses must never reach it."""

    async def by_candidate(self, candidate_id):
        return None


gate = PublicationGate(LicenseMatrix(DefaultLicenseGrants.TABLE))
spec = build_spec()
candidate = build_candidate()
# No download URL, so the refuse path is the only one left past the decision: neither run
# reaches the digest, Saleor or category port, which is why they are None below and why a
# bridge that accepts the decision ends in a printed line rather than a traceback.
candidate.download_url = None
record = build_record(evidence_kinds=(EvidenceKind.LLM_EXTRACTION, EvidenceKind.SPDX_MATCH))
assert gate.decide(spec, record).publishable is False, 'the fixture record must be refused'

decision = GateDecision(
    candidate_id=candidate.id, publishable=True, reasons=(), record=record
)
bridge = PublicationBridge(
    gate=gate, saleor=None, entries=EmptyCatalogue(), categories=None, digest=None
)
asyncio.run(bridge.apply(candidate, decision, spec, datetime(2026, 9, 23, tzinfo=UTC)))

print('NOT RAISED: the bridge accepted a decision the gate refuses')
raise SystemExit(1)
`)

const guardOutput = output(guardProbe)
const guardEvidence =
  guardOutput
    .split(/\r?\n/)
    .filter((line) => line.includes('RightsDeniedError') || line.includes('NOT RAISED'))
    .slice(-1)[0] || '(no verdict in the probe output)'
check(
  'the bridge raises RightsDeniedError for a decision the gate refuses',
  guardEvidence.includes('RightsDeniedError'),
  guardEvidence.trim()
)

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

// The alias table has to come from the tree being inspected. A static import read this
// checkout's table, so a target whose own table was missing an alias passed whenever this
// checkout happened to have it: the check compared the target's mcp.json against the wrong
// file. `context7` exists here and the injected tree's table is empty, so it must fail there.
const aliasDrift = sandbox()
write(
  aliasDrift,
  '.cursor/mcp.json',
  `${JSON.stringify(
    {
      mcpServers: {
        context7: { command: 'node', args: ['${workspaceFolder}/.cursor/mcp/run-mcp.cjs', 'context7'] }
      }
    },
    null,
    2
  )}\n`
)
write(aliasDrift, '.cursor/mcp/mcp-aliases.cjs', 'module.exports = Object.freeze({})\n')
const aliasDriftRun = runScript('scripts/harness-status.mjs', ['--root', aliasDrift])
const aliasDriftOutput = output(aliasDriftRun)
check(
  'reads the alias table from the inspected tree, not from this checkout',
  /FAIL\s+context7: alias "context7"/.test(aliasDriftOutput),
  aliasDriftOutput.split(/\r?\n/).find((line) => line.includes('context7: alias')) || '(no alias line)'
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
