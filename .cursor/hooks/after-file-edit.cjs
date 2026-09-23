#!/usr/bin/env node
/**
 * afterFileEdit - append one line to the edit ledger.
 *
 * Why this exists
 * ---------------
 * When a session goes wrong, the first question is what was actually written and in
 * what order. `git diff` answers "what is different now" but not "what did the agent
 * touch, and when" - a change that was written and then reverted leaves no trace there.
 * The ledger is that trace, and it costs one append per edit.
 *
 * It is observe-only on purpose: it records, it never judges, and it never blocks an
 * edit. Anything that gates a write belongs in a preToolUse hook where a denial is a
 * decision the agent can read.
 *
 * The payload
 * -----------
 * `file_path`, `conversation_id` and `edits` arrive in the hook input, and it arrives with a
 * UTF-8 BOM. This hook used to parse stdin directly, fail on that BOM, fall back to `{}` and
 * record a line with an empty path and an empty conversation id - for every edit, silently.
 * `lib/hook-io.cjs` reads the payload correctly; `scripts/selftest.mjs` now sends the BOM so
 * the regression is caught rather than trusted.
 *
 * Ledger: .velmor/edit-ledger/<YYYY-MM-DD>.log, one tab-separated line per edit -
 * `<ISO timestamp>\t<conversation_id>\t<repo-relative path>` - git-ignored.
 * `VELMOR_EDIT_LEDGER=0` disables it.
 *
 * Contract: hook input JSON on stdin, `{}` on stdout, always exit 0. A failed append
 * must not surface as an edit failure, so every path that can throw is guarded - but
 * the failure is reported on stderr rather than swallowed silently, because a ledger
 * that quietly stopped recording is worse than no ledger.
 */

const fs = require('fs')
const path = require('path')

const hookIo = require('./lib/hook-io.cjs')

function main() {
  if (process.env.VELMOR_EDIT_LEDGER === '0') {
    process.stdout.write('{}')
    return
  }

  const input = hookIo.readPayload()
  const root = hookIo.workspaceRoot(input)
  const edited = input.file_path || ''
  const directory = path.join(root, '.velmor', 'edit-ledger')

  try {
    fs.mkdirSync(directory, { recursive: true })
    const day = new Date().toISOString().slice(0, 10)
    // Repository-relative with forward slashes, so a ledger written on Windows reads the
    // same as one written on macOS or Linux.
    const relative = (path.isAbsolute(edited) ? path.relative(root, edited) : edited).replace(
      /\\/g,
      '/'
    )
    fs.appendFileSync(
      path.join(directory, `${day}.log`),
      `${new Date().toISOString()}\t${input.conversation_id || '-'}\t${relative}\n`
    )
  } catch (error) {
    console.error(`after-file-edit: could not append to the edit ledger: ${error.message}`)
  }

  process.stdout.write('{}')
}

main()
