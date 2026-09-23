#!/usr/bin/env node
/**
 * Serialized MCP launcher.
 *
 * Why this exists
 * ---------------
 * Cursor starts every configured MCP server at the same moment. When several of them
 * are `npx -y <package>` and the package is not in the npm cache yet, the concurrent
 * installs race inside the shared npm cache and fail with errors that look like a
 * broken server rather than a cache collision. This launcher resolves a cached local
 * copy when one exists and otherwise takes a cross-process lock so only one install
 * runs at a time.
 *
 * Usage (from .cursor/mcp.json):
 *   node .cursor/mcp/run-mcp.cjs <alias> [...extraArgs]
 *
 * Resolution order:
 *   1. A local node_modules copy of the package, run directly with node.
 *   2. `npx -y <package>` under the lock.
 *
 * The alias -> package table lives in `mcp-aliases.cjs` and is shared with the
 * harness sensors, so a package is named in exactly one place.
 *
 * Contract: stdio is inherited. The child's exit code becomes this process's exit
 * code, so a failed server surfaces in the MCP log instead of hanging.
 */

const { spawn } = require('child_process')
const fs = require('fs')
const os = require('os')
const path = require('path')

const aliases = require('./mcp-aliases.cjs')

const ROOT = path.resolve(__dirname, '..', '..')
const LOCK_PATH = path.join(os.tmpdir(), 'velmor-mcp-npx.lock')
const STALE_LOCK_MS = 300_000
const LOCK_WAIT_MS = 180_000

const requested = process.argv[2]
if (!requested) {
  console.error('usage: node run-mcp.cjs <alias|package> [...args]')
  process.exit(1)
}

const pkg = aliases[requested] || requested
const extraArgs = process.argv.slice(3)

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function run(command, args, { shell = false } = {}) {
  const child = spawn(command, args, {
    stdio: 'inherit',
    shell,
    cwd: ROOT,
    env: process.env,
    windowsHide: true
  })
  child.on('exit', (code, signal) => {
    if (signal) process.exit(1)
    process.exit(code === null ? 1 : code)
  })
  child.on('error', (error) => {
    console.error(`run-mcp: failed to start ${command}: ${error.message}`)
    process.exit(1)
  })
}

/** A locally installed copy needs no network and cannot collide in the npm cache. */
function resolveLocalEntry() {
  const manifestPath = path.join(ROOT, 'node_modules', ...pkg.split('/'), 'package.json')
  if (!fs.existsSync(manifestPath)) return null

  let manifest
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
  } catch (error) {
    console.error(`run-mcp: cannot read ${manifestPath}: ${error.message}`)
    return null
  }

  const bin = manifest.bin
  let relative = null
  if (typeof bin === 'string') relative = bin
  else if (bin && typeof bin === 'object') relative = bin[Object.keys(bin)[0]]
  if (!relative && manifest.main) relative = manifest.main
  if (!relative) return null

  const absolute = path.join(path.dirname(manifestPath), relative)
  return fs.existsSync(absolute) ? absolute : null
}

/** Hold one lock across the install so a second server waits instead of racing. */
async function acquireLock() {
  const started = Date.now()
  for (;;) {
    try {
      const handle = fs.openSync(LOCK_PATH, 'wx')
      fs.writeFileSync(handle, String(process.pid))
      fs.closeSync(handle)
      return
    } catch (error) {
      if (Date.now() - started > LOCK_WAIT_MS) {
        console.error(`run-mcp: timed out waiting for ${LOCK_PATH}`)
        process.exit(1)
      }
      // A lock left behind by a killed process would block every server forever.
      try {
        if (Date.now() - fs.statSync(LOCK_PATH).mtimeMs > STALE_LOCK_MS) {
          fs.unlinkSync(LOCK_PATH)
        }
      } catch (statError) {
        // The holder released it between the two calls; the next iteration wins the race.
      }
      await sleep(400)
    }
  }
}

function releaseLock() {
  try {
    fs.unlinkSync(LOCK_PATH)
  } catch (error) {
    // Already gone; nothing to release.
  }
}

async function main() {
  const entry = resolveLocalEntry()
  if (entry) {
    run(process.execPath, [entry, ...extraArgs])
    return
  }

  await acquireLock()
  process.on('exit', releaseLock)
  run(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['-y', pkg, ...extraArgs],
    { shell: true }
  )
}

main()
