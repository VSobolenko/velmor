// lint-feedback: after an edit to a Python file, run ruff on it and hand the
// result back to the agent as context.
//
// This exists so a lint violation is fixed in the same turn it was introduced,
// instead of surfacing at commit time or, worse, being found by the reviewer.
// `[tool.ruff.lint].select` in pyproject.toml is kept at zero violations by
// construction, so any output from this hook is new code.
//
// It is advisory: it never denies, and every failure path is silent. A broken
// lint tool must not block editing.
//
// Contract: tool-call JSON on stdin, { "additional_context": ... } on stdout,
// exit 0.

const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const TIMEOUT_MS = 45000

const hookIo = require('./lib/hook-io.cjs')

function readInput() {
  return hookIo.readStdin()
}

function targetPath(toolInput) {
  return toolInput.path || tool_input.file_path || toolInput.filePath || toolInput.target_file || ''
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

  const target = targetPath(payload.tool_input || payload.toolInput || {})
  if (!target || path.extname(target) !== '.py') {
    silent()
    return
  }

  let output
  try {
    output = execFileSync('uv', ['run', '--quiet', 'ruff', 'check', '--no-cache', target], {
      cwd: process.cwd(),
      timeout: TIMEOUT_MS,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe']
    })
  } catch (error) {
    if (error.status === 1 && error.stdout) {
      report(
        'ruff reports violations in the file you just edited. Fix them before moving on:\n\n' +
          error.stdout
      )
      return
    }
    // ruff is missing, timed out, or exited for an unrelated reason: stay quiet.
    silent()
    return
  }

  if (output && output.trim() !== '') {
    report('ruff output for the file you just edited:\n\n' + output)
  }
  silent()
}

main()
