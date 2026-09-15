#!/usr/bin/env node
// setup-mcp: report what in .cursor/mcp.json is ready on this machine and what
// still needs a human.
//
// .cursor/mcp.json is committed, so a teammate gets the same servers on clone and
// `npx -y` installs the package on first use. What is NOT automatic, by design:
//
//   1. Each developer enables the servers in Cursor Settings -> MCP and reloads
//      the window. That is per-machine state, not repository state, and no script
//      can do it for you.
//   2. A server that needs a credential is per-developer. The config holds an
//      `${env:VAR}` interpolation, never the value.
//
// This script only inspects. It resolves each launcher, names the package that
// will be installed, and reports which environment variables are unset *in this
// shell*. It does not install anything and does not launch a server: doing that
// for eight servers on every check would take minutes and defeat the point.
//
// Usage: node scripts/setup-mcp.mjs
// Exit code 1 when a launcher is missing; credentials unset are reported, not
// treated as a failure, because a fresh shell legitimately has none.

import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const CONFIG_PATH = join(ROOT, '.cursor', 'mcp.json')
const ENV_REFERENCE = /\$\{env:([A-Z0-9_]+)\}/g

function isExecutableAvailable(name) {
  const finder = process.platform === 'win32' ? 'where' : 'which'
  const result = spawnSync(finder, [name], { encoding: 'utf8', shell: false })
  return result.status === 0
}

// The package a launcher will install. For `npx -y pkg` it is the first
// non-flag argument; for `uvx --from pkg entry` it is the argument after --from.
function resolvePackage(args) {
  const fromIndex = args.indexOf('--from')
  if (fromIndex !== -1 && args[fromIndex + 1] !== undefined) return args[fromIndex + 1]
  const candidate = args.find((arg) => !arg.startsWith('-') && !arg.startsWith('${'))
  return candidate === undefined ? '(unresolved)' : candidate
}

function referencedEnvVars(server) {
  const found = new Set()
  for (const match of JSON.stringify(server).matchAll(ENV_REFERENCE)) found.add(match[1])
  return [...found].sort()
}

function inspect(server) {
  if (typeof server.url === 'string') {
    return {
      kind: 'remote',
      transport: server.url,
      launcher: null,
      pkg: null,
      env: referencedEnvVars(server)
    }
  }

  const args = Array.isArray(server.args) ? server.args : []
  const launcher = server.command
  return {
    kind: 'local',
    transport: args.join(' '),
    launcher,
    pkg: resolvePackage(args),
    env: referencedEnvVars(server)
  }
}

function printRow(name, report, missingLauncher, unset) {
  const status = missingLauncher
    ? 'MISSING LAUNCHER'
    : unset.length > 0
      ? 'NEEDS YOUR VALUE'
      : 'ready'
  console.log(`${name}`)
  console.log(`  transport  ${report.kind}: ${report.transport}`)
  if (report.launcher !== null) console.log(`  launcher   ${report.launcher}`)
  if (report.pkg !== null) console.log(`  package    ${report.pkg}`)
  if (report.env.length > 0) console.log(`  env        ${report.env.join(', ')}`)
  console.log(`  status     ${status}`)
  console.log('')
}

function main() {
  let config
  try {
    config = JSON.parse(readFileSync(CONFIG_PATH, 'utf8'))
  } catch (error) {
    console.error(`cannot read ${CONFIG_PATH}: ${error.message}`)
    process.exit(1)
  }

  const servers = config.mcpServers || {}
  const names = Object.keys(servers).sort()
  if (names.length === 0) {
    console.error('no mcpServers configured')
    process.exit(1)
  }

  console.log(`MCP servers declared in .cursor/mcp.json: ${names.length}`)
  console.log('')

  const brokenLaunchers = []

  for (const name of names) {
    const report = inspect(servers[name])
    const missingLauncher =
      report.launcher !== null && !isExecutableAvailable(report.launcher)
    const unset = report.env.filter((key) => !process.env[key])
    if (missingLauncher) brokenLaunchers.push(`${name} (${report.launcher})`)
    printRow(name, report, missingLauncher, unset)
  }

  console.log('Manual steps, once per machine:')
  console.log('  1. Cursor Settings -> MCP -> enable the servers listed above, then reload.')
  console.log('  2. Set the variables reported as NEEDS YOUR VALUE in your own environment.')
  console.log('     Never write a credential into .cursor/mcp.json; use ${env:VAR}.')
  console.log('')

  if (brokenLaunchers.length > 0) {
    console.error(`launcher not found on PATH: ${brokenLaunchers.join(', ')}`)
    console.error('install uv (provides uvx) or Node (provides npx) and retry')
    process.exit(1)
  }

  console.log('every launcher resolves; nothing else to do here')
}

main()
