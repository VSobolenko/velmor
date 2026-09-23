/**
 * hook-io - read a hook's stdin payload the way the runtime actually sends it.
 *
 * Why this exists
 * ---------------
 * Cursor writes hook input to stdin as UTF-8 **with a byte-order mark** on Windows, and
 * `JSON.parse` rejects a leading U+FEFF outright. Measured on a real payload:
 *
 *   firstBytesHex: efbbbf7b22636f6e766572736174    (efbbbf = UTF-8 BOM, then {"conversat)
 *   indexOfBrace:  1                               (the "{" is one character in)
 *   parseError:    Unexpected token ..., is not valid JSON
 *
 * Every hook read stdin with `JSON.parse(fs.readFileSync(0, 'utf8'))` inside a `try` that
 * fell back to `{}`. So on this platform every hook received nothing, and did nothing, while
 * reporting success. A hardcoded live Stripe secret in a `Write` payload was measured going
 * straight through `secret-guard.cjs` with `{"permission":"allow"}`.
 *
 * The failure was invisible because `scripts/selftest.mjs` feeds hooks clean JSON - the
 * payload the runtime does NOT send. A sensor tested against an imagined input is not a
 * sensor. The selftest now sends the BOM too, so this cannot come back unnoticed.
 *
 * Rules for anything that reads hook input: use `readPayload()`, never `JSON.parse` on raw
 * stdin, and never swallow a parse failure silently - the `console.error` below is the
 * difference between a loud bug and a silent one.
 *
 * Failure mode: explicit allow. A hook input that cannot be read is reported on stderr and
 * treated as empty; each hook then applies its own documented fallback, which for the write
 * guards is "no payload, nothing to check".
 */

const fs = require('fs')
const path = require('path')

/** The BOM Cursor prefixes the payload with, stripped so JSON.parse can see the object. */
const BOM = /^\uFEFF/

/** Raw stdin, BOM removed. `''` when stdin cannot be read at all. */
function readStdin() {
  try {
    return (fs.readFileSync(0, 'utf8') || '').replace(BOM, '')
  } catch (error) {
    return ''
  }
}

/**
 * The parsed payload, or `{}` when there is nothing usable. A parse failure is reported on
 * stderr rather than swallowed: a hook that silently stops working is the defect this file
 * was written to end.
 */
function readPayload() {
  const raw = readStdin()
  if (raw.trim() === '') return {}
  try {
    return JSON.parse(raw)
  } catch (error) {
    console.error(`hook-io: hook stdin is not valid JSON (${error.message}); treating as empty`)
    return {}
  }
}

/**
 * The workspace root from the payload.
 *
 * Cursor sends a URL-ish root on Windows - `"/d:/Python/Velmor"` - and `path.join` turns that
 * into `"\d:\Python\Velmor"`, which is a real path on the current drive root and not the
 * workspace. Normalising the drive form here is what keeps a hook from writing a ledger into
 * a directory that does not exist.
 */
function workspaceRoot(payload, fallback) {
  const roots = (payload && payload.workspace_roots) || []
  const raw = String(roots[0] || '')
  if (raw === '') return fallback || process.cwd()
  return /^\/[a-zA-Z]:[\\/]/.test(raw) ? raw.slice(1) : raw
}

/**
 * The write target of a tool call as a repository-relative path.
 *
 * A real tool call carries an **absolute** path - measured, `tool_input.file_path` is
 * `d:\Python\Velmor\packages\...` - while the lists these guards match against are
 * repository-relative. Comparing one form to the other made the comparison fail for every
 * real write, so each guard reached its allow branch without ever looking at the target:
 * `codex-gate`, `policy-guard` and `ui-guard` were all inert in production while their
 * checks, fed repository-relative paths, passed. Resolving against the workspace root is
 * what makes a repository-relative list match the payload the runtime actually sends. A path
 * outside the workspace keeps its absolute form and so matches no repository-relative entry.
 */
function workspaceRelative(filePath, root) {
  const raw = String(filePath).replace(/\\/g, '/').replace(/^\.\//, '')
  // The url-ish drive form (`/d:/...`) is what `workspace_roots` carries and can arrive as a
  // write target too, so strip it before asking `path` anything.
  const absolute = /^\/[a-zA-Z]:[\\/]/.test(raw) ? raw.slice(1) : raw
  if (!path.isAbsolute(absolute)) return absolute
  const relative = path.relative(path.resolve(root), path.resolve(absolute)).replace(/\\/g, '/')
  return relative.startsWith('../') || path.isAbsolute(relative) ? absolute : relative
}

module.exports = { readStdin, readPayload, workspaceRoot, workspaceRelative }
