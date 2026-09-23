#!/usr/bin/env node
/**
 * Velmor Codex worker runner.
 *
 * Why this exists
 * ---------------
 * The Codex MCP server (`codex` / `codex-reply`) is the right transport for short
 * dialogue, but an MCP request has a timeout. A real implementation or verification
 * task runs for minutes, the MCP call dies mid-flight and the work is lost. This
 * runner drives the Codex CLI non-interactively and keeps every artefact on disk, so
 * a worker can be started, polled, read and resumed long after the call that started
 * it has returned.
 *
 * It runs in the foreground on purpose. The orchestrator's shell tool is what
 * backgrounds long jobs, so several workers can run in parallel (each in its own
 * worktree, or with disjoint write sets) without any process-detaching tricks.
 *
 * A worker's own report is never evidence. Read its diff, run the gate yourself.
 *
 * Usage
 * -----
 *   node scripts/codex-run.mjs run    --id <id> --prompt-file harness/codex/prompts/<file>.md
 *   node scripts/codex-run.mjs review --id <id> [--base <branch> | --uncommitted]
 *   node scripts/codex-run.mjs status [--id <id>]
 *   node scripts/codex-run.mjs list
 *   node scripts/codex-run.mjs last   --id <id> [--chars 4000]
 *   node scripts/codex-run.mjs log    --id <id> [--lines 60]
 *   node scripts/codex-run.mjs resume --id <id> --prompt-file <file>
 *
 * `run` and `review` options:
 *   --cwd <dir>          working root for Codex (default: repo root)
 *   --model <name>       pass through to `-m` (default: gpt-5.6-terra)
 *   --effort <level>     none|low|medium|high|xhigh|max (default: medium)
 *   --sandbox <mode>     read-only|workspace-write (default: workspace-write)
 *   --timeout-min <n>    kill the worker after n minutes (default: none)
 *   --label <text>       human note stored in the meta file
 *
 * Ledger for worker <id>, all git-ignored:
 *   .velmor/codex/<id>.meta.json   arguments, status, exit code, classified signal
 *   .velmor/codex/<id>.log         stdout
 *   .velmor/codex/<id>.err         stderr, including the `session id:` line
 *   .velmor/codex/<id>.last.md     the worker's final message
 *   .velmor/codex/<id>.exit.json   the exit record
 *
 * Prompts are NOT in the ledger directory. They are authored by the orchestrating agent
 * and belong in `harness/codex/prompts/`, because `.velmor/` is listed in `.cursorignore`
 * and Cursor denies an agent both read and write on an ignored path. A prompt written
 * there cannot be created by the agent that has to write it, and a prompt nobody can read
 * back is not a reviewable task statement. Keep the ledger in `.velmor/` (bulky, transient,
 * ignored) and the prompts in `harness/` (small, committed, diffable).
 *
 * `danger-full-access` is refused here by design. A durable, unattended worker is
 * exactly where unrestricted filesystem and process authority is most dangerous, and
 * `workspace-write` covers every Build and Verify task. Use the MCP tool, which
 * carries a human in the loop, if full access is genuinely required.
 */

import { spawn, spawnSync } from 'node:child_process'
import { appendFileSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { classifyFailure } from './lib/codex-signals.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const STATE = join(ROOT, '.velmor', 'codex')
const PROMPTS = join(ROOT, 'harness', 'codex', 'prompts')
const LAUNCHER = join(ROOT, '.cursor', 'mcp', 'codex-launcher.cjs')

const EFFORTS = ['none', 'low', 'medium', 'high', 'xhigh', 'max']
const SANDBOXES = ['read-only', 'workspace-write']

/**
 * The model every worker runs unless `--model` overrides it.
 *
 * Pinned here rather than inherited from `~/.codex/config.toml`, so the model is a property of
 * this repository and does not change when a machine's global config does. `gpt-5.6-sol`, the
 * CLI default on the machine this was written on, is described by the CLI's own catalog as the
 * model "for complex work"; a bounded task from a written prompt is not that, and the tier was
 * consuming a ChatGPT plan's quota in a handful of calls. `gpt-5.6-terra` is the catalog's
 * "balanced model for straightforward work", which is the profile of the work delegated here.
 * The cheaper `gpt-5.6-luna` and `gpt-reserve` are deliberately not the default: an independent
 * reader that is too weak to find the defect defeats the point of having a second reader.
 *
 * `codex debug models` renders the catalog this was chosen from.
 */
const DEFAULT_MODEL = 'gpt-5.6-terra'

const argv = process.argv.slice(2)
const cmd = argv[0]

const metaPath = (id) => join(STATE, `${id}.meta.json`)
const logPath = (id) => join(STATE, `${id}.log`)
const errPath = (id) => join(STATE, `${id}.err`)
const lastPath = (id) => join(STATE, `${id}.last.md`)
const exitPath = (id) => join(STATE, `${id}.exit.json`)

/**
 * Whether a pid still names a live process.
 *
 * `process.kill(pid, 0)` is the only existence probe Node offers and it throws when the target
 * is gone, so the catch is the contract rather than a swallowed failure: `EPERM` means the
 * process exists but belongs to another user, and every other code means it does not exist.
 *
 * This is the deliberate twin of `processAlive` in `.cursor/hooks/codex-gate.cjs`, and the two
 * must change together. They cannot share one definition: the gate is CommonJS and this runner
 * is ESM, and a hook cannot await a dynamic import. If the gate is ever converted to ESM, move
 * this into `scripts/lib/` and import it from both instead of keeping a copy.
 */
function processAlive(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    return error.code === 'EPERM'
  }
}

function arg(name, fallback = null) {
  const index = argv.indexOf(name)
  if (index === -1) return fallback
  return argv[index + 1] ?? fallback
}

function has(name) {
  return argv.includes(name)
}

function fail(message) {
  console.error(`codex-run: ${message}`)
  process.exit(1)
}

function ensureDirs() {
  mkdirSync(STATE, { recursive: true })
  mkdirSync(PROMPTS, { recursive: true })
}

function readMeta(id) {
  const file = metaPath(id)
  if (!existsSync(file)) fail(`unknown worker id: ${id} (no ${file})`)
  return JSON.parse(readFileSync(file, 'utf8'))
}

function readText(file) {
  return existsSync(file) ? readFileSync(file, 'utf8') : ''
}

/** The last `lines` of a ledger file; empty when the file does not exist yet. */
function tail(file, lines) {
  if (!existsSync(file)) return ''
  return readFileSync(file, 'utf8').split(/\r?\n/).slice(-lines).join('\n')
}

function validateCommon(meta) {
  if (!EFFORTS.includes(meta.effort)) {
    fail(`--effort must be one of ${EFFORTS.join('|')}, got "${meta.effort}"`)
  }
  if (meta.sandbox === 'danger-full-access') {
    fail(
      'refusing --sandbox danger-full-access: a durable unattended worker must not have\n' +
        'unrestricted filesystem and process authority. Use workspace-write, or drive the\n' +
        'task through the codex MCP tool where a human is in the loop.'
    )
  }
  if (!SANDBOXES.includes(meta.sandbox)) {
    fail(`--sandbox must be one of ${SANDBOXES.join('|')}, got "${meta.sandbox}"`)
  }
  if (meta.timeoutMin !== null && !(Number(meta.timeoutMin) > 0)) {
    fail(`--timeout-min must be a positive number of minutes, got "${meta.timeoutMin}"`)
  }
  if (!existsSync(LAUNCHER)) {
    fail(`missing ${LAUNCHER}; the Codex channel is not wired up`)
  }
}

function newMeta(id, kind) {
  return {
    id,
    kind,
    label: arg('--label', ''),
    cwd: resolve(ROOT, arg('--cwd', ROOT)),
    model: arg('--model', DEFAULT_MODEL),
    effort: arg('--effort', 'medium'),
    sandbox: arg('--sandbox', 'workspace-write'),
    timeoutMin: arg('--timeout-min', null),
    log: logPath(id),
    err: errPath(id),
    lastMessage: lastPath(id),
    status: 'running',
    startedAt: new Date().toISOString(),
    pid: process.pid
  }
}

/**
 * Launch Codex with the recorded arguments, stream both pipes into the ledger, and
 * record the exit. `args` excludes the launcher: stdin carries the prompt, or is empty
 * when the worker runs with Codex's own default instructions (a plain review).
 */
function launch(id, meta, args) {
  appendFileSync(meta.log, `\n=== codex-run ${id} (${meta.kind}) @ ${meta.startedAt} ===\n`)

  const child = spawn(process.execPath, [LAUNCHER, ...args], {
    cwd: meta.cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true
  })

  const err = []
  child.stdout.on('data', (chunk) => appendFileSync(meta.log, chunk))
  child.stderr.on('data', (chunk) => {
    err.push(chunk)
    appendFileSync(meta.err, chunk)
  })

  let timer = null
  if (meta.timeoutMin) {
    timer = setTimeout(() => {
      console.error(`codex-run: ${id} exceeded --timeout-min ${meta.timeoutMin}, killing`)
      child.kill('SIGKILL')
    }, Number(meta.timeoutMin) * 60_000)
  }

  child.stdin.end(meta.promptFile ? readFileSync(meta.promptFile, 'utf8') : '')

  child.on('error', (error) => {
    if (timer) clearTimeout(timer)
    finish(meta, null, `spawn error: ${error.message}`)
  })
  child.on('exit', (code) => {
    if (timer) clearTimeout(timer)
    finish(meta, code, err.join(''))
  })
}

function finish(meta, code, errText) {
  const stdout = readText(meta.log)
  // Only a non-zero exit is a failure to classify. Classifying a successful run produced a
  // false AUTH_ERROR on a worker that had done its job correctly, and a signal on a `DONE`
  // worker sends the orchestrator down the fallback ladder for no reason.
  const signal = code === 0 ? null : classifyFailure(`${errText || ''}\n${stdout}`)
  writeFileSync(
    exitPath(meta.id),
    `${JSON.stringify(
      {
        id: meta.id,
        kind: meta.kind,
        exitCode: code,
        signal,
        finishedAt: new Date().toISOString()
      },
      null,
      2
    )}\n`
  )
  meta.status = code === 0 ? 'done' : signal ? 'blocked' : 'failed'
  meta.exitCode = code
  meta.signal = signal
  writeFileSync(metaPath(meta.id), `${JSON.stringify(meta, null, 2)}\n`)

  console.log('')
  console.log(`codex-run: ${meta.id} exit=${code}${signal ? ` signal=${signal}` : ''}`)
  if (existsSync(meta.lastMessage)) {
    const text = readFileSync(meta.lastMessage, 'utf8')
    console.log('--- final message ---')
    console.log(text.length > 4000 ? `...${text.slice(-4000)}` : text)
  } else {
    console.log('--- no final message; stderr tail ---')
    console.log(tail(meta.err, 30))
  }
  process.exit(code === 0 ? 0 : 1)
}

function promptFileArgument() {
  const given = arg('--prompt-file')
  if (!given) fail('--prompt-file is required; prompts live in harness/codex/prompts/')
  const full = resolve(ROOT, given)
  if (!existsSync(full)) fail(`prompt file not found: ${full}`)
  return full
}

function run() {
  ensureDirs()
  const id = arg('--id')
  if (!id) fail('run requires --id')
  if (existsSync(metaPath(id))) {
    fail(`worker "${id}" already exists; use resume, or pick a new id`)
  }

  const meta = newMeta(id, 'run')
  meta.promptFile = promptFileArgument()
  validateCommon(meta)
  writeFileSync(metaPath(id), `${JSON.stringify(meta, null, 2)}\n`)

  const args = [
    'exec',
    '--cd',
    meta.cwd,
    '--sandbox',
    meta.sandbox,
    '--color',
    'never',
    '--output-last-message',
    meta.lastMessage,
    '-c',
    `model_reasoning_effort="${meta.effort}"`
  ]
  if (meta.model) args.push('-m', meta.model)
  args.push('-')

  launch(id, meta, args)
}

/**
 * Independent review of the working tree through `codex exec review`. It needs no
 * prompt file: the prompt is the review instructions, passed on stdin.
 */
function review() {
  ensureDirs()
  const id = arg('--id')
  if (!id) fail('review requires --id')
  if (existsSync(metaPath(id))) {
    fail(`worker "${id}" already exists; use resume, or pick a new id`)
  }

  const base = arg('--base', null)
  const scope = base ? ['--base', base] : ['--uncommitted']
  const instructions = arg('--instructions')
  const instructionsFile = instructions ? resolve(ROOT, instructions) : null
  if (instructionsFile && !existsSync(instructionsFile)) {
    fail(`instructions file not found: ${instructionsFile}`)
  }

  const meta = newMeta(id, 'review')
  meta.scope = base ? `base:${base}` : 'uncommitted'
  // Absent instructions, Codex reviews with its own default review prompt.
  meta.promptFile = instructionsFile
  validateCommon(meta)
  writeFileSync(metaPath(id), `${JSON.stringify(meta, null, 2)}\n`)

  // No `--color` here, unlike `run`: `codex exec review` does not accept it, and passing it
  // made every review exit 2 before the model was reached. Verified against the installed CLI
  // with `codex exec review --help`; the accepted flags are listed in `harness/codex-workers.md`.
  //
  // `review` has no `--sandbox` flag either, so the policy is reachable only through `-c`, and
  // without it the reviewer inherited the CLI default `workspace-write`. An independent reader
  // must not be able to write: `harness/dual-agent.md` names a read-only Codex worker as one of
  // the independent readers, so the sandbox is pinned here the way `resume` already pins it.
  const args = [
    'exec',
    'review',
    ...scope,
    '--output-last-message',
    meta.lastMessage,
    '-c',
    `model_reasoning_effort="${meta.effort}"`,
    '-c',
    'sandbox_mode="read-only"'
  ]
  if (meta.model) args.push('-m', meta.model)
  // `-` means "read the prompt from stdin", and the CLI refuses to combine a PROMPT with
  // `--uncommitted`. A review with no `--instructions` therefore passes no PROMPT at all and
  // runs Codex's own review prompt, which is what `meta.promptFile` being null already says.
  if (meta.promptFile) args.push('-')

  launch(id, meta, args)
}

function status() {
  ensureDirs()
  const one = arg('--id')
  const ids = one ? [one] : listIds()
  if (ids.length === 0) {
    console.log('no workers found')
    return
  }

  for (const id of ids) {
    const file = metaPath(id)
    if (!existsSync(file)) {
      console.log(`${'MISSING'.padEnd(18)} ${id}`)
      continue
    }
    const meta = JSON.parse(readFileSync(file, 'utf8'))
    let state = meta.status || 'unknown'
    if (existsSync(exitPath(id))) {
      const record = JSON.parse(readFileSync(exitPath(id), 'utf8'))
      state =
        record.exitCode === 0
          ? 'DONE'
          : record.signal
            ? `BLOCKED(${record.signal})`
            : `FAILED(${record.exitCode})`
    } else if (meta.pid && !processAlive(meta.pid)) {
      // A worker that was killed - by an operator, by a closed terminal, by a machine restart -
      // never writes an exit record, so without this the ledger kept calling it `running` for
      // hours. Measured: two workers killed during a session still read `running` after 155 and
      // 140 minutes, while `process.kill(pid, 0)` said the pids were gone.
      //
      // `LOST` is deliberately not `FAILED`: nothing observed how it ended, so the outcome is
      // unknown and must not be reported as a failure the worker chose. It is also not
      // `running`, because a reader deciding whether to wait or to re-dispatch would wait
      // forever. A `resume` is still valid for a lost worker: it resumes by session id.
      state = `LOST(${meta.pid})`
    }
    const minutes = ((Date.now() - Date.parse(meta.startedAt)) / 60_000).toFixed(1)
    const hasLast = existsSync(lastPath(id)) ? 'last=yes' : 'last=no'
    console.log(
      `${String(state).padEnd(18)} ${id.padEnd(24)} ${minutes}m ${hasLast} ${meta.kind} ${
        meta.label || ''
      }`
    )
  }
}

function listIds() {
  if (!existsSync(STATE)) return []
  return readdirSync(STATE)
    .filter((name) => name.endsWith('.meta.json'))
    .map((name) => name.replace(/\.meta\.json$/, ''))
    .sort()
}

function showLast(id, chars) {
  if (!id) fail('--id is required')
  const file = lastPath(id)
  if (!existsSync(file)) {
    console.log('(no final message yet)')
    return
  }
  const text = readFileSync(file, 'utf8')
  console.log(text.length > chars ? `...${text.slice(-chars)}` : text)
}

/**
 * The Codex CLI prints `session id: <uuid>` on stderr. Resuming by that exact id
 * matters: several workers can share one working directory, so `--last` would resume
 * whichever session finished most recently, which may be a different task.
 */
function sessionIdOf(id) {
  const match = readText(errPath(id)).match(/session id:\s*([0-9a-fA-F-]{8,})/i)
  return match ? match[1] : null
}

function resume() {
  ensureDirs()
  const id = arg('--id')
  if (!id) fail('resume requires --id')
  const meta = readMeta(id)
  meta.promptFile = promptFileArgument()
  appendFileSync(meta.log, `\n=== resume @ ${new Date().toISOString()} ===\n`)

  const sessionId = sessionIdOf(id)
  if (!sessionId) {
    fail(
      `no session id in ${errPath(id)}. Cannot resume safely; --last would pick whichever\n` +
        'session finished most recently, not this worker. Start a new worker instead.'
    )
  }

  // `codex exec resume` accepts neither --sandbox nor --cd, so the resumed turn inherits
  // the root recorded when the session started - but NOT the sandbox. Without the override
  // below it silently falls back to the CLI default, `workspace-write` with approval
  // `never`, so resuming a read-only Verify worker would hand it write access. `-c` is the
  // only channel that reaches the sandbox policy on resume; Codex echoes the effective
  // value as `sandbox: ...` in its start banner, which is how this was confirmed.
  const args = [
    'exec',
    'resume',
    sessionId,
    '--output-last-message',
    meta.lastMessage,
    '-c',
    `model_reasoning_effort="${meta.effort}"`,
    '-c',
    `sandbox_mode="${meta.sandbox}"`
  ]
  if (meta.model) args.push('-m', meta.model)
  args.push('-')

  const result = spawnSync(process.execPath, [LAUNCHER, ...args], {
    cwd: meta.cwd,
    input: readFileSync(meta.promptFile, 'utf8'),
    encoding: 'utf8',
    windowsHide: true
  })
  appendFileSync(meta.log, result.stdout || '')
  appendFileSync(meta.err, result.stderr || '')
  finish(meta, result.status, result.stderr || '')
}

function usage() {
  console.log(
    [
      'Velmor Codex worker runner (foreground; let your shell tool background it)',
      '',
      '  run    --id <id> --prompt-file <file> [--cwd dir] [--model m] [--effort lvl]',
      '         [--sandbox read-only|workspace-write] [--timeout-min n] [--label text]',
      '  review --id <id> [--base <branch> | --uncommitted] [--instructions <file>]',
      '         [--model m] [--effort lvl] [--label text]',
      '  status [--id <id>]',
      '  list',
      '  last   --id <id> [--chars n]',
      '  log    --id <id> [--lines n]',
      '  resume --id <id> --prompt-file <file>',
      '',
      'See harness/codex-workers.md for the prompt contract and the failure ladder.'
    ].join('\n')
  )
}

switch (cmd) {
  case 'run':
    run()
    break
  case 'review':
    review()
    break
  case 'status':
  case 'list':
    status()
    break
  case 'last':
    showLast(arg('--id'), Number(arg('--chars', '4000')))
    break
  case 'log':
    console.log(tail(logPath(arg('--id')), Number(arg('--lines', '60'))))
    console.log('--- stderr ---')
    console.log(tail(errPath(arg('--id')), Number(arg('--lines', '30'))))
    break
  case 'resume':
    resume()
    break
  default:
    usage()
    process.exit(cmd ? 1 : 0)
}
