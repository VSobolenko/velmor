#!/usr/bin/env node
/**
 * harness-status: is the agent harness complete and usable on this machine?
 *
 * Why this exists
 * ---------------
 * The harness is a set of files that only fail silently. A hook whose script was
 * renamed, a subagent mirrored into `.cursor/` but not into `.codex/`, an alias that
 * exists in `mcp.json` but not in the alias table, a change directory with no
 * `tasks.md` - none of these produce an error at the moment they break. They surface
 * later as an agent that quietly stopped being governed, or a plan that cannot be
 * executed. This script is the sensor that makes them visible now.
 *
 * It checks three different kinds of thing, in order of how loud the failure is:
 *
 *   - FAIL - the harness is incomplete or internally inconsistent, and an agent will
 *     behave worse than the rules describe. Exit code 1.
 *   - WARN - a machine-level dependency is missing. The harness is correct; this
 *     machine cannot exercise part of it. Exit code stays 0.
 *   - INFO - an inventory line, for reporting the harness's shape.
 *
 * It inspects only. It installs nothing, enables nothing in Cursor, and launches no
 * server: those are per-machine actions a human takes once.
 *
 * Usage:
 *   node scripts/harness-status.mjs
 *   node scripts/harness-status.mjs --root <dir>   # inspect another tree (used by
 *                                                 # scripts/selftest.mjs)
 */

import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const argv = process.argv.slice(2)
const rootFlag = argv.indexOf('--root')
const ROOT =
  rootFlag === -1
    ? resolve(dirname(fileURLToPath(import.meta.url)), '..')
    : resolve(argv[rootFlag + 1] || '.')

/**
 * The alias table of the tree being inspected, not of this checkout.
 *
 * A static `import` here resolves relative to this script, so it always read the alias table
 * of the checkout the script lives in. With `--root` the two are different trees, and the
 * alias check below then compared the target's `mcp.json` against the wrong table: a target
 * whose own `mcp-aliases.cjs` was missing an alias passed whenever this checkout happened to
 * have it. `scripts/selftest.mjs` drives this script with `--root`, so the blind spot was
 * reachable; a sensor that reads the wrong tree is not a sensor.
 */
const aliasPath = join(ROOT, '.cursor', 'mcp', 'mcp-aliases.cjs')
const aliases = existsSync(aliasPath) ? createRequire(import.meta.url)(aliasPath) : {}

// The servers the documented workflows name. `/ux-verify` needs a browser,
// `/review` and the Codex channel need `codex`, the harness reads library docs
// through `context7`, and the local storefront data lives behind `postgres`.
// Everything else in mcp.json is reported, not required.
const REQUIRED_MCP = ['context7', 'playwright', 'codex', 'postgres']

// Every surface the harness contracts reference. A file listed here is load-bearing:
// a rule, a command or `AGENTS.md` points at it by path.
const REQUIRED_FILES = [
  'AGENTS.md',
  'CLAUDE.md',
  '.gitignore',
  '.cursorignore',
  'package.json',
  '.cursor/hooks.json',
  '.cursor/hooks/lib/hook-io.cjs',
  '.cursor/mcp.json',
  '.cursor/mcp/mcp-aliases.cjs',
  '.cursor/mcp/run-mcp.cjs',
  '.cursor/mcp/codex-launcher.cjs',
  'scripts/harness-status.mjs',
  'scripts/selftest.mjs',
  'scripts/setup-mcp.mjs',
  'scripts/codex-run.mjs',
  'scripts/sync-agents.mjs',
  'scripts/lib/codex-signals.mjs',
  'harness/README.md',
  'harness/ambition.md',
  'harness/cursor-surface.md',
  'harness/dual-agent.md',
  'harness/codex-workers.md',
  'harness/codex/prompts/README.md',
  'harness/codex/prompts/smoke-test.md',
  'harness/codex/prompts/build-task.md',
  'harness/lessons.md',
  'openspec/config.yaml'
]

// Rule files that must exist, because other documents cite them by number.
const REQUIRED_RULES = [
  '.cursor/rules/00-project-rules.mdc',
  '.cursor/rules/01-security-secrets.mdc',
  '.cursor/rules/02-architecture-layers.mdc',
  '.cursor/rules/03-error-handling.mdc',
  '.cursor/rules/04-python.mdc',
  '.cursor/rules/05-agent-graphs.mdc',
  '.cursor/rules/06-rights-engine.mdc',
  '.cursor/rules/07-product-surface.mdc',
  '.cursor/rules/08-evidence-and-sensors.mdc'
]

// Commands the harness documents as entry points.
const REQUIRED_COMMANDS = [
  'ship',
  'review',
  'rights-verify',
  'ux-verify',
  'eval',
  'diagnose',
  'improve-harness',
  'harness-status'
]

let hasFailure = false

function line(status, message) {
  console.log(`${status.padEnd(8)} ${message}`)
  if (status === 'FAIL') hasFailure = true
}

function section(title) {
  console.log(`\n## ${title}`)
}

function readText(relativePath) {
  try {
    return readFileSync(join(ROOT, relativePath), 'utf8').replace(/^\uFEFF/, '')
  } catch (error) {
    return null
  }
}

function entries(relativePath) {
  try {
    return readdirSync(join(ROOT, relativePath), { withFileTypes: true }).sort((left, right) =>
      left.name.localeCompare(right.name)
    )
  } catch (error) {
    return []
  }
}

function files(relativePath, extension) {
  return entries(relativePath)
    .filter((entry) => entry.isFile() && (!extension || entry.name.endsWith(extension)))
    .map((entry) => entry.name)
}

function directories(relativePath) {
  return entries(relativePath)
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
}

function joinNames(names) {
  return names.length > 0 ? names.join(', ') : '(none)'
}

function run(command, args, timeout = 30_000) {
  const result = spawnSync(command, args, {
    cwd: ROOT,
    encoding: 'utf8',
    shell: false,
    timeout,
    windowsHide: true
  })
  return {
    ok: result.status === 0,
    output: `${result.stdout || ''}${result.stderr || ''}`.trim(),
    error: result.error
  }
}

function firstLine(value) {
  return (
    String(value || '')
      .split(/\r?\n/)
      .map((item) => item.trim())
      .find(Boolean) || ''
  )
}

console.log('# Velmor harness status')
console.log(`root: ${ROOT}`)

section('Environment')
const nodeMajor = Number(process.versions.node.split('.')[0])
line(nodeMajor >= 20 ? 'PASS' : 'FAIL', `node ${process.versions.node} (>= 20 required)`)

const uv = run('uv', ['--version'])
line(uv.ok ? 'PASS' : 'FAIL', uv.ok ? `uv ${firstLine(uv.output).replace(/^uv /, '')}` : 'uv is not on PATH')

const git = run('git', ['--version'])
line(git.ok ? 'PASS' : 'FAIL', git.ok ? firstLine(git.output) : 'git is not on PATH')

// Not a failure: the unit suite needs no database, and a checkout without Docker is
// still fully usable for the product work.
const docker = run('docker', ['--version'])
line(
  docker.ok ? 'INFO' : 'WARN',
  docker.ok ? firstLine(docker.output) : 'docker is not on PATH; local Postgres and Redis cannot be started'
)

section('Harness surfaces')
for (const relativePath of REQUIRED_FILES) {
  line(existsSync(join(ROOT, relativePath)) ? 'PASS' : 'FAIL', relativePath)
}
for (const relativePath of REQUIRED_RULES) {
  line(existsSync(join(ROOT, relativePath)) ? 'PASS' : 'FAIL', relativePath)
}

section('Inventory')
const commands = files('.cursor/commands', '.md').map((name) => name.replace(/\.md$/, ''))
const rules = files('.cursor/rules', '.mdc')
const hookScripts = files('.cursor/hooks', '.cjs')
const cursorAgents = files('.cursor/agents', '.md')
const skillDirectories = directories('.cursor/skills')
const skillManifests = skillDirectories.filter((name) =>
  existsSync(join(ROOT, '.cursor', 'skills', name, 'SKILL.md'))
)
line('INFO', `.cursor/commands/*.md: ${commands.length} (${joinNames(commands)})`)
line('INFO', `.cursor/rules/*.mdc: ${rules.length}`)
line('INFO', `.cursor/hooks/*.cjs: ${hookScripts.length}`)
line('INFO', `.cursor/agents/*.md: ${cursorAgents.length}`)
line('INFO', `.cursor/skills/*/SKILL.md: ${skillManifests.length} of ${skillDirectories.length}`)

for (const required of REQUIRED_COMMANDS) {
  line(
    commands.includes(required) ? 'PASS' : 'FAIL',
    `.cursor/commands/${required}.md`
  )
}

for (const skill of skillDirectories) {
  if (skillManifests.includes(skill)) continue
  line('FAIL', `.cursor/skills/${skill}/SKILL.md is missing`)
}

section('Subagent mirrors')
// Cursor reads `.cursor/agents/`, `.claude/agents/` (Claude compatibility) and
// `.codex/agents/` (Codex compatibility). A subagent that exists only in one of them
// is invisible to the other two harnesses, which is the drift this catches.
if (cursorAgents.length === 0) {
  line('FAIL', '.cursor/agents/ holds no subagents')
}
for (const agent of cursorAgents) {
  const missing = ['.claude/agents', '.codex/agents'].filter(
    (directory) => !existsSync(join(ROOT, directory, agent))
  )
  line(
    missing.length === 0 ? 'PASS' : 'FAIL',
    missing.length === 0
      ? `${agent}: mirrored in .claude/agents and .codex/agents`
      : `${agent}: missing from ${missing.join(', ')}`
  )
}

section('Hooks wiring')
let hooks = null
const hooksText = readText('.cursor/hooks.json')
if (hooksText === null) {
  line('FAIL', 'cannot read .cursor/hooks.json')
} else {
  try {
    hooks = JSON.parse(hooksText)
  } catch (error) {
    line('FAIL', `.cursor/hooks.json is invalid JSON: ${error.message}`)
  }
}

if (hooks) {
  const events = Object.keys(hooks.hooks || {})
  line('INFO', `events wired: ${joinNames(events)}`)
  for (const event of events) {
    for (const definition of hooks.hooks[event] || []) {
      const command = String(definition.command || '')
      const script = command.split(/\s+/).pop()
      line(
        existsSync(join(ROOT, script)) ? 'PASS' : 'FAIL',
        `${event}: ${script}`
      )
    }
  }
  for (const required of ['sessionStart', 'preToolUse', 'beforeShellExecution', 'beforeMCPExecution', 'postToolUse', 'afterFileEdit', 'stop']) {
    if (!events.includes(required)) line('WARN', `no hook wired for "${required}"`)
  }

  // The Codex-first requirement is the one constraint whose absence is invisible in a diff:
  // an agent that implements the work itself passes every other gate in this list. So its
  // wiring is checked by name, not left to "some hook file exists".
  const preToolUseCommands = (hooks.hooks.preToolUse || [])
    .map((definition) => String(definition.command || ''))
    .join(' ')
  line(
    preToolUseCommands.includes('codex-gate.cjs') ? 'PASS' : 'FAIL',
    'preToolUse wires codex-gate.cjs: product code needs a Codex worker behind it'
  )
}

section('MCP configuration')
let mcp = null
const mcpText = readText('.cursor/mcp.json')
if (mcpText === null) {
  line('FAIL', 'cannot read .cursor/mcp.json')
} else {
  try {
    mcp = JSON.parse(mcpText)
  } catch (error) {
    line('FAIL', `.cursor/mcp.json is invalid JSON: ${error.message}`)
  }
}

if (mcp) {
  const servers = mcp.mcpServers || {}
  const names = Object.keys(servers).sort()
  line('INFO', `servers declared: ${names.length} (${joinNames(names)})`)

  for (const required of REQUIRED_MCP) {
    line(Boolean(servers[required]) ? 'PASS' : 'FAIL', `required server: ${required}`)
  }

  // An alias that no longer exists in the table is a server that cannot start, and the
  // error it produces at load time does not name the missing alias.
  for (const name of names) {
    const args = Array.isArray(servers[name].args) ? servers[name].args : []
    const head = String(args[0] || '').replace('${workspaceFolder}', ROOT).replace(/\\/g, '/')
    if (!head.endsWith('/.cursor/mcp/run-mcp.cjs')) continue
    const alias = args[1]
    line(
      Object.prototype.hasOwnProperty.call(aliases, alias) ? 'PASS' : 'FAIL',
      `${name}: alias "${alias}" resolves in .cursor/mcp/mcp-aliases.cjs`
    )
  }
}

section('Codex worker channel')
const launcher = '.cursor/mcp/codex-launcher.cjs'
if (!existsSync(join(ROOT, launcher))) {
  line('FAIL', `${launcher} is missing`)
} else {
  const codex = run(process.execPath, [join(ROOT, launcher), '--version'], 60_000)
  line(
    codex.ok ? 'PASS' : 'WARN',
    codex.ok
      ? `Codex CLI ${firstLine(codex.output)}`
      : `Codex CLI unresolved: ${firstLine(codex.output) || codex.error?.message || 'unknown error'}`
  )
}

const workerDirectory = join(ROOT, '.velmor', 'codex')
const workers = existsSync(workerDirectory)
  ? readdirSync(workerDirectory).filter((name) => name.endsWith('.meta.json')).length
  : 0
line('INFO', `recorded Codex workers: ${workers}`)

section('Concurrent writers')
// A single working tree with two agents in it produces test results that are not measurements.
// That was observed directly: a pytest run reported 14 failures in `test_curation.py` and three
// minutes later the same command reported 689 passed, because a second session was mid-edit -
// `curation.py` changed at 20:20:42 while the run was in flight. The edit ledger records the
// conversation id per edit, so the condition is readable instead of invisible.
const ledgerDirectory = join(ROOT, '.velmor', 'edit-ledger')
const WRITER_WINDOW_MINUTES = 30
const recentWriters = new Map()
if (existsSync(ledgerDirectory)) {
  const cutoff = Date.now() - WRITER_WINDOW_MINUTES * 60_000
  for (const name of readdirSync(ledgerDirectory).filter((entry) => entry.endsWith('.log'))) {
    for (const line_ of (readText(join('.velmor', 'edit-ledger', name)) || '').split(/\r?\n/)) {
      const [stamp, conversation, file] = line_.split('\t')
      if (!stamp || !file) continue
      if (Date.parse(stamp) < cutoff) continue
      const key = conversation || '-'
      if (!recentWriters.has(key)) recentWriters.set(key, new Set())
      recentWriters.get(key).add(file)
    }
  }
}

const writers = [...recentWriters.keys()].filter((key) => key !== '-')
if (writers.length > 1) {
  const detail = writers
    .map((key) => `${key.slice(0, 8)} (${recentWriters.get(key).size} files)`)
    .join(', ')
  line(
    'WARN',
    `${writers.length} sessions edited files in the last ${WRITER_WINDOW_MINUTES} minutes: ${detail}. ` +
      'A test run from this tree is not a measurement while they overlap.'
  )
} else {
  line(
    'PASS',
    writers.length === 1
      ? `one writer session in the last ${WRITER_WINDOW_MINUTES} minutes (${writers[0].slice(0, 8)})`
      : `no writer sessions recorded in the last ${WRITER_WINDOW_MINUTES} minutes`
  )
}

section('Harness state is ignored')
const gitignore = readText('.gitignore') || ''
const ignoredState = gitignore
  .split(/\r?\n/)
  .map((entry) => entry.trim())
  .some((entry) => entry === '.velmor/' || entry === '.velmor')
line(ignoredState ? 'PASS' : 'FAIL', '.gitignore ignores .velmor/ (Codex ledger, prompts, edit ledger)')

section('OpenSpec')
const specs = directories('openspec/specs')
const changes = directories('openspec/changes').filter((name) => name !== 'archive')
line('INFO', `specs: ${specs.length} (${joinNames(specs)})`)
line('INFO', `active changes: ${changes.length} (${joinNames(changes)})`)
for (const change of changes) {
  const tasks = existsSync(join(ROOT, 'openspec', 'changes', change, 'tasks.md'))
  line(tasks ? 'PASS' : 'FAIL', `${change}: tasks.md ${tasks ? 'present' : 'missing'}`)
}

// `config.yaml` carries the project context and the rules every proposal, spec, design and
// task list is written against. When it does not parse, OpenSpec *warns and ignores it* and
// still reports every change as valid - so the contract silently disappears from all future
// work and nothing fails. That is why this scans the output instead of trusting the exit
// code. The warning is emitted by `validate`, and only by `validate`, which is why this runs
// it rather than a cheaper command.
// `openspec` is an npm CLI, so on Windows it is a `.cmd` shim rather than an executable, and
// Node refuses to spawn one directly. `cmd.exe /d /s /c` is used instead of `shell: true`,
// which would concatenate the arguments into a command string and emit DEP0190. `uv`, `git`
// and `docker` are real executables and stay spawn-only, with no shell involved.
//
// A config that OpenSpec cannot read is the worst kind of harness failure: it reports
// "could not parse ... ignoring it" (or "ignoring this artifact's rules" for one bad section)
// and still exits 0 with every change valid. The project contract then disappears from all
// future work with nothing failing, so the output is scanned rather than the exit code trusted.
const openspecInvocation =
  process.platform === 'win32'
    ? [process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', 'openspec', 'validate', '--strict', '--all']]
    : ['openspec', ['validate', '--strict', '--all']]
const openspec = run(...openspecInvocation, 120_000)
const ignoredConfig = openspec.output.match(
  /.*(could not parse|ignoring this artifact|ignoring it).*/i
)
if (openspec.error) {
  line('WARN', 'openspec CLI is not on PATH; the spec contract cannot be checked here')
} else if (ignoredConfig) {
  line('FAIL', `OpenSpec is ignoring part of openspec/config.yaml: ${ignoredConfig[0].trim()}`)
} else if (!openspec.ok) {
  line('FAIL', `openspec validate --strict --all failed: ${firstLine(openspec.output)}`)
} else {
  const totals = openspec.output
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .find((entry) => entry.startsWith('Totals:'))
  line('PASS', `openspec validate --strict --all: ${totals || 'ok'}`)
}

console.log(`\nVERDICT: ${hasFailure ? 'NOT READY' : 'READY'}`)
if (hasFailure) {
  console.log('Fix the FAIL lines above, then run this again. Run `node scripts/selftest.mjs`')
  console.log('if a harness script itself looks wrong.')
}
process.exitCode = hasFailure ? 1 : 0
