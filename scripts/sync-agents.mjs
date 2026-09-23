#!/usr/bin/env node
/**
 * Mirror the project subagents into every runtime that reads them.
 *
 * Why this exists
 * ---------------
 * Cursor reads `.cursor/agents/` and also `.claude/agents/` (Claude compatibility) and
 * `.codex/agents/` (Codex compatibility). A subagent defined in only one of them is invisible
 * to the other two, so the same task is governed by different instructions depending on which
 * agent was asked - and the drift produces no error anywhere.
 *
 * `harness-status.mjs` detects that drift and fails. This script is what fixes it, so nobody
 * hand-copies a file and diverges on the second edit. `.cursor/` is the source; the other two
 * are copies of it, never edited directly.
 *
 * An extra file in a mirror directory is stale, not harmless: it is still loadable by that
 * runtime, so it would keep a retired subagent reachable. Those are removed.
 *
 * Usage:
 *   node scripts/sync-agents.mjs            # write the mirrors
 *   node scripts/sync-agents.mjs --check    # report drift, change nothing, exit 1 if any
 */

import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync
} from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SOURCE = join(ROOT, '.cursor', 'agents')
const MIRRORS = [join(ROOT, '.claude', 'agents'), join(ROOT, '.codex', 'agents')]

const checkOnly = process.argv.includes('--check')

if (!existsSync(SOURCE)) {
  console.error(`sync-agents: ${SOURCE} does not exist; there is nothing to mirror`)
  process.exit(1)
}

const agents = readdirSync(SOURCE)
  .filter((name) => name.endsWith('.md'))
  .sort()

if (agents.length === 0) {
  console.error(`sync-agents: ${SOURCE} holds no subagents`)
  process.exit(1)
}

let drift = false
const report = []

for (const mirror of MIRRORS) {
  const relative = mirror.slice(ROOT.length + 1).replace(/\\/g, '/')
  const existing = existsSync(mirror)
    ? readdirSync(mirror).filter((name) => name.endsWith('.md'))
    : []

  for (const agent of agents) {
    const from = join(SOURCE, agent)
    const to = join(mirror, agent)
    const same = existsSync(to) && readFileSync(from, 'utf8') === readFileSync(to, 'utf8')
    if (same) continue
    drift = true
    if (checkOnly) {
      report.push(`${relative}/${agent}: ${existsSync(to) ? 'differs' : 'missing'}`)
      continue
    }
    mkdirSync(mirror, { recursive: true })
    copyFileSync(from, to)
    report.push(`${relative}/${agent}: ${existsSync(to) ? 'updated' : 'copied'}`)
  }

  for (const stale of existing.filter((name) => !agents.includes(name))) {
    drift = true
    if (checkOnly) {
      report.push(`${relative}/${stale}: stale, not in .cursor/agents/`)
      continue
    }
    rmSync(join(mirror, stale))
    report.push(`${relative}/${stale}: removed, no longer in .cursor/agents/`)
  }
}

if (checkOnly) {
  if (drift) {
    console.error('subagent mirrors are out of date:')
    for (const entry of report) console.error(`  - ${entry}`)
    console.error('Run `node scripts/sync-agents.mjs` to fix.')
    process.exit(1)
  }
  console.log(`${agents.length} subagents mirrored in ${MIRRORS.length} runtimes; in sync`)
} else if (drift) {
  console.log(`synced ${agents.length} subagents into ${MIRRORS.length} runtimes:`)
  for (const entry of report) console.log(`  ${entry}`)
} else {
  console.log(`${agents.length} subagents already in sync across ${MIRRORS.length} runtimes`)
}
