#!/usr/bin/env node
/**
 * sessionStart - inject the harness orientation into every new chat.
 *
 * What this is for
 * ----------------
 * The rules and `AGENTS.md` are already in context: Cursor loads `.cursor/rules/*.mdc`
 * whose frontmatter says `alwaysApply`, and `CLAUDE.md` references `AGENTS.md`. So this
 * hook does not repeat them. It supplies the two things that are *not* always-on and
 * that a session otherwise has to go looking for:
 *
 *   1. which harness entry points exist (they are not discoverable from the product
 *      code, and an agent that does not know about `/ship` will improvise);
 *   2. the current harness state - which OpenSpec changes are open, and the most recent
 *      entry in `harness/lessons.md`, which is the factory's memory of defects that
 *      already happened once.
 *
 * The state part is deliberately read at start: it is the difference between an agent
 * that knows a change is half-applied and one that re-plans work already done.
 *
 * Contract: session input JSON on stdin, `{ env, additional_context }` JSON on stdout,
 * exit 0. Fire-and-forget: it must never block a session, so every unexpected path
 * degrades to a shorter message rather than an error. That is also why the file reads
 * below are individually guarded - one unreadable file must not cost the whole
 * orientation.
 */

const fs = require('fs')
const path = require('path')

const hookIo = require('./lib/hook-io.cjs')

function readIfPresent(file, max) {
  try {
    if (!fs.existsSync(file)) return ''
    const text = fs.readFileSync(file, 'utf8')
    return text.length > max ? `${text.slice(0, max)}\n[...truncated]` : text
  } catch (error) {
    return ''
  }
}

/** Active OpenSpec changes, by directory. `archive/` is history, not work in flight. */
function activeChanges(root) {
  try {
    return fs
      .readdirSync(path.join(root, 'openspec', 'changes'), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && entry.name !== 'archive')
      .map((entry) => entry.name)
      .sort()
  } catch (error) {
    return []
  }
}

/**
 * Date the session, so `codex-gate.cjs` can tell "a Codex worker ran for this work" from "a
 * Codex worker ran at some point in the repository's history". A failed write must not fail
 * the session: the gate falls back to a time window when the marker is absent, which is
 * stricter than allowing, not weaker.
 */
function markSession(root) {
  try {
    const directory = path.join(root, '.velmor', 'session')
    fs.mkdirSync(directory, { recursive: true })
    fs.writeFileSync(path.join(directory, 'epoch'), new Date().toISOString())
  } catch (error) {
    console.error(`session-start: could not write the session marker: ${error.message}`)
  }
}

/** The most recent append-only entry in harness/lessons.md. */
function latestLesson(root) {
  const text = readIfPresent(path.join(root, 'harness', 'lessons.md'), 200000)
  if (!text) return ''
  const headings = [...text.matchAll(/^### .+$/gm)]
  if (headings.length === 0) return ''
  const start = headings[headings.length - 1].index
  const body = text.slice(start).trim()
  return body.length > 1200 ? `${body.slice(0, 1200)}\n[...truncated]` : body
}

function main() {
  const input = hookIo.readPayload()
  const root = hookIo.workspaceRoot(input)

  markSession(root)

  const changes = activeChanges(root)
  const lesson = latestLesson(root)

  const lines = [
    '=== VELMOR HARNESS (injected at session start) ===',
    'Velmor is a rights-verified marketplace: a good is listed only after the publication',
    'gate decides PUBLISHABLE, and that verdict is a pure function of its inputs. Nothing a',
    'model says is a verdict, and no refusal is wrapped in try/except. Full contract: AGENTS.md.',
    '',
    'WHO IMPLEMENTS: Codex. Product code under packages/, velmor/ and storefront/ is written by',
    'a Codex worker, and you verify the diff. Cursor implements only after a classified Codex',
    'failure (RATE_LIMITED / CONTEXT_LIMIT / AUTH_ERROR) or two failed attempts, and you say so',
    'when that happens. Exception, never delegated: packages/services/src/rights/** and',
    'screening/**, which a human approves. `.cursor/hooks/codex-gate.cjs` refuses a product-code',
    'write with no worker behind it, so delegate instead of hitting the denial.',
    '',
    'Entry points you are expected to use instead of improvising:',
    '- contract: openspec/ (proposal, specs, tasks) - /opsx-propose, /opsx-apply, /opsx-archive',
    '- end to end: /ship <task> - stops only at plan approval and at integration',
    '- implement: node scripts/codex-run.mjs run --id <id> --prompt-file harness/codex/prompts/<p>.md',
    '  prompts start from harness/codex/prompts/build-task.md; a worker self-report is NEVER evidence',
    '- review gate: /review (bugbot + security-review)',
    '- domain runtime: /rights-verify (does the gate still refuse what it must)',
    '- buyer surface runtime: /ux-verify (screenshots are the evidence)',
    '- harness health: node scripts/harness-status.mjs; self-test: node scripts/selftest.mjs',
    '- harness state is git-ignored under .velmor/ (Codex ledger, prompts, edit ledger)',
    ''
  ]

  lines.push(
    changes.length > 0
      ? `Active OpenSpec changes: ${changes.join(', ')}`
      : 'Active OpenSpec changes: none - propose one before implementing.'
  )
  lines.push('')
  lines.push(lesson ? `Most recent harness lesson (harness/lessons.md):\n${lesson}` : 'harness/lessons.md has no entries yet.')
  lines.push('')
  lines.push('Before claiming anything is done: run the command and quote its output.')

  process.stdout.write(
    JSON.stringify({
      env: { VELMOR_ROOT: root, VELMOR_HARNESS: '1' },
      additional_context: lines.join('\n')
    })
  )
}

main()
