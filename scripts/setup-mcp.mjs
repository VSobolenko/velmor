#!/usr/bin/env node
// setup-mcp: report what in .cursor/mcp.json is ready on this machine and what still
// needs a human.
//
// .cursor/mcp.json is committed, so a teammate gets the same servers on clone and the
// package installs on first use. What is NOT automatic, by design:
//
//   1. Each developer enables the servers in Cursor Settings -> MCP and reloads the
//      window. That is per-machine state, not repository state, and no script can do
//      it for you.
//   2. A server that needs a credential is per-developer. The config holds an
//      ${env:VAR} interpolation, never the value.
//
// This script only inspects. It resolves each launcher, names the package that will be
// installed, and reports which environment variables are unset *in this shell*. It
// does not install anything and does not launch a server: doing that for eleven
// servers on every check would take minutes and defeat the point.
//
// It also fails on a misconfiguration that no runtime error would name clearly: an
// alias in mcp.json that is missing from mcp-aliases.cjs, or a credential-shaped value
// written into the config instead of interpolated from the environment.
//
// Usage: node scripts/setup-mcp.mjs
// Exit code 1 when a launcher is missing or a server is misconfigured. Credentials
// unset in this shell are reported, not treated as a failure, because a fresh shell
// legitimately has none.

import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import aliases from '../.cursor/mcp/mcp-aliases.cjs'

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const CONFIG_PATH = join(ROOT, '.cursor', 'mcp.json')
const ENV_REFERENCE = /\$\{env:([A-Z0-9_]+)\}/g
const CREDENTIAL_KEY = /(key|token|secret|password|authorization)/i

function isExecutableAvailable(name) {
  const finder = process.platform === 'win32' ? 'where' : 'which'
  const result = spawnSync(finder, [name], { encoding: 'utf8', shell: false })
  return result.status === 0
}

function expandWorkspace(value) {
  return String(value).replace('${workspaceFolder}', ROOT).replace(/\\/g, '/')
}

// The package a launcher will install. For `npx -y pkg` it is the first non-flag
// argument; for `uvx --from pkg entry` it is the argument after --from.
function resolvePackage(args) {
  const fromIndex = args.indexOf('--from')
  if (fromIndex !== -1 && args[fromIndex + 1] !== undefined) return args[fromIndex + 1]
  const candidate = args.find((arg) => !arg.startsWith('-') && !arg.startsWith('${'))
  return candidate === undefined ? '(unresolved)' : candidate
}

// `.cursor/mcp.json` names an alias; `.cursor/mcp/run-mcp.cjs` resolves it. Reporting
// the package therefore means following one indirection.
function describeLocal(server) {
  const args = Array.isArray(server.args) ? server.args : []
  const head = expandWorkspace(args[0] || '')

  if (head.endsWith('/.cursor/mcp/run-mcp.cjs')) {
    const alias = args[1]
    const pkg = Object.prototype.hasOwnProperty.call(aliases, alias) ? aliases[alias] : null
    return { adapter: 'run-mcp', alias, pkg, transport: `npx -y ${pkg || alias}` }
  }
  if (head.endsWith('/.cursor/mcp/codex-launcher.cjs')) {
    return {
      adapter: 'codex-launcher',
      alias: null,
      pkg: '(Codex CLI, resolved from the editor extension at start)',
      transport: args.slice(1).join(' ')
    }
  }
  return { adapter: null, alias: null, pkg: resolvePackage(args), transport: args.join(' ') }
}

function referencedEnvVars(server) {
  const found = new Set()
  for (const match of JSON.stringify(server).matchAll(ENV_REFERENCE)) found.add(match[1])
  return [...found].sort()
}

// A credential key whose value is a literal rather than an ${env:...} reference.
function inlineCredentials(server) {
  const found = []
  for (const section of ['env', 'headers']) {
    const entries = server[section]
    if (!entries || typeof entries !== 'object') continue
    for (const [key, value] of Object.entries(entries)) {
      if (!CREDENTIAL_KEY.test(key)) continue
      if (!String(value).includes('${env:')) found.push(`${section}.${key}`)
    }
  }
  return found
}

function inspect(server) {
  if (typeof server.url === 'string') {
    return {
      kind: 'remote',
      transport: server.url,
      launcher: null,
      pkg: null,
      env: referencedEnvVars(server),
      inline: inlineCredentials(server)
    }
  }
  const local = describeLocal(server)
  return {
    kind: 'local',
    transport: local.transport,
    launcher: server.command,
    pkg: local.pkg,
    adapter: local.adapter,
    alias: local.alias,
    env: referencedEnvVars(server),
    inline: inlineCredentials(server)
  }
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

  const problems = []

  for (const name of names) {
    const report = inspect(servers[name])
    const missingLauncher = report.launcher !== null && !isExecutableAvailable(report.launcher)
    const unknownAlias = report.adapter === 'run-mcp' && report.pkg === null
    const unset = report.env.filter((key) => !process.env[key])

    if (missingLauncher) problems.push(`${name}: launcher "${report.launcher}" is not on PATH`)
    if (unknownAlias) {
      problems.push(
        `${name}: alias "${report.alias}" is not in .cursor/mcp/mcp-aliases.cjs, so no package can be resolved`
      )
    }
    for (const entry of report.inline) {
      problems.push(`${name}: ${entry} holds a literal credential; use \${env:VAR} instead`)
    }

    const status = missingLauncher
      ? 'MISSING LAUNCHER'
      : unknownAlias
        ? 'UNKNOWN ALIAS'
        : unset.length > 0
          ? 'NEEDS YOUR VALUE'
          : 'ready'

    console.log(name)
    console.log(`  transport  ${report.kind}: ${report.transport}`)
    if (report.launcher !== null) console.log(`  launcher   ${report.launcher}`)
    if (report.pkg !== null) console.log(`  package    ${report.pkg}`)
    if (report.env.length > 0) console.log(`  env        ${report.env.join(', ')}`)
    console.log(`  status     ${status}`)
    console.log('')
  }

  console.log('Manual steps, once per machine:')
  console.log('  1. Cursor Settings -> MCP -> enable the servers above, then reload the window.')
  console.log('  2. Export the variables reported as NEEDS YOUR VALUE in your own environment.')
  console.log('     Never write a credential into .cursor/mcp.json; use ${env:VAR}.')
  console.log('')

  if (problems.length > 0) {
    console.error('misconfigured:')
    for (const problem of problems) console.error(`  - ${problem}`)
    process.exit(1)
  }

  console.log('every launcher resolves; nothing else to do here')
}

main()
