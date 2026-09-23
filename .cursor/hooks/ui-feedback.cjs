// ui-feedback: after an edit to the storefront's copy or a storefront page, run
// the dictionary parity check and hand the result back as context.
//
// This exists because the failure it addresses is invisible in a diff: a string
// added to one locale file and forgotten in another still builds, still renders
// in the default locale, and only shows up as a missing label for a buyer
// reading another language. Catching it in the turn that introduces it is the
// cheapest possible fix.
//
// It is advisory: it never denies, and every failure path is silent. A missing or
// broken check script must not block editing.
//
// Contract: tool-call JSON on stdin, { "additional_context": ... } on stdout,
// exit 0.

const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const TIMEOUT_MS = 20000
const CHECK_SCRIPT = 'storefront/scripts/check-i18n.mjs'

const hookIo = require('./lib/hook-io.cjs')

function readInput() {
  return hookIo.readStdin()
}

function targetPath(toolInput) {
  return toolInput.path || tool_input.file_path || toolInput.filePath || tool_input.target_file || ''
}

function normalise(filePath) {
  return String(filePath).replace(/\\/g, '/').replace(/^\.\//, '')
}

// The locale files and anything a buyer renders. A change to a Python file, a
// stylesheet or a config is not this hook's business.
function isGuardedSource(candidate) {
  if (!candidate.startsWith('storefront/')) return false
  if (candidate.includes('node_modules/') || candidate.includes('.next/')) return false
  if (candidate.includes('/lib/i18n/')) return candidate.endsWith('.json')
  return /\.(tsx|ts)$/.test(candidate)
}

function silent() {
  process.exit(0)
}

function report(context) {
  process.stdout.write(JSON.stringify({ additional_context: context }))
  process.exit(0)
}

function main() {
  let payload
  try {
    payload = JSON.parse(readInput())
  } catch (error) {
    silent()
    return
  }

  const toolName = payload.tool_name || payload.toolName || ''
  if (!/^(Write|StrReplace)$/.test(toolName)) {
    silent()
    return
  }

  const toolInput = payload.tool_input || payload.toolInput || {}
  const candidate = normalise(targetPath(toolInput))
  if (!isGuardedSource(candidate)) {
    silent()
    return
  }

  if (!fs.existsSync(path.join(process.cwd(), CHECK_SCRIPT))) {
    silent()
    return
  }

  try {
    execFileSync('node', [CHECK_SCRIPT], {
      cwd: process.cwd(),
      timeout: TIMEOUT_MS,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe']
    })
  } catch (error) {
    if (error.status === 1 && (error.stdout || error.stderr)) {
      report(
        'The locale dictionaries are out of sync after your edit. Add every missing ' +
          'key to all three files before moving on:\n\n' +
          (error.stdout || '') +
          (error.stderr || '')
      )
      return
    }
    // The script is missing a dependency, timed out, or failed for its own
    // reason: stay quiet rather than report a problem that is not the edit's.
    silent()
    return
  }

  silent()
}

main()
