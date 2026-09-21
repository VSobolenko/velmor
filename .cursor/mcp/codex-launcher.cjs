#!/usr/bin/env node
/**
 * Codex MCP launcher.
 *
 * Codex ships inside a *versioned* editor-extension directory, e.g.
 *   <extensions>/openai.chatgpt-26.721.30844-win32-x64/bin/windows-x86_64/codex.exe
 * The version segment changes on every extension update, and the extensions
 * directory itself can live anywhere (portable installs, non-default drives).
 * Hardcoding either in mcp.json would silently break the MCP server after an
 * update, so this launcher resolves the newest installed Codex binary at
 * runtime and execs it with the given args.
 *
 * Usage (from mcp.json):
 *   node .cursor/mcp/codex-launcher.cjs mcp-server
 *
 * Resolution order:
 *   1. CODEX_BIN environment variable (full path to the binary) — always wins.
 *   2. Editor extension directories, discovered from:
 *        - the Windows registry (VS Code / Cursor / Windsurf / Trae uninstall keys)
 *        - running editor processes
 *        - well-known per-user locations
 *      The newest `openai.chatgpt-*` / `openai.codex-*` directory wins.
 *
 * If nothing is found it exits non-zero with a clear message, so the failure
 * surfaces in the MCP server log instead of hanging.
 */

const { spawn, execFileSync } = require('child_process')
const fs = require('fs')
const os = require('os')
const path = require('path')

const EXE = process.platform === 'win32' ? 'codex.exe' : 'codex'
const EXTENSION_PREFIXES = ['openai.chatgpt-', 'openai.codex-']

// Locations of the binary *inside* an extension directory, by platform.
const PLATFORM_SUBPATHS = [
  path.join('bin', 'windows-x86_64', EXE),
  path.join('bin', 'x86_64-unknown-linux-musl', EXE),
  path.join('bin', 'aarch64-unknown-linux-musl', EXE),
  path.join('bin', 'aarch64-apple-darwin', EXE),
  path.join('bin', 'x86_64-apple-darwin', EXE),
  path.join('bin', EXE),
  EXE
]

// Editor installation directories whose `extensions/` we should inspect.
function editorInstallDirs() {
  const dirs = []

  // --- Windows registry: uninstall entries carry InstallLocation.
  if (process.platform === 'win32') {
    const keys = [
      'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
      'HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
      'HKLM\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall'
    ]
    for (const key of keys) {
      let out = ''
      try {
        out = execFileSync('reg', ['query', key, '/s', '/v', 'InstallLocation'], {
          encoding: 'utf8',
          windowsHide: true,
          stdio: ['ignore', 'pipe', 'ignore']
        })
      } catch (e) {
        continue
      }
      for (const line of out.split(/\r?\n/)) {
        const m = line.match(/^\s*InstallLocation\s+REG_[A-Z_]+\s+(.+?)\s*$/)
        if (m) dirs.push(m[1].trim())
      }
    }

    // --- Running editors reveal their install dir directly.
    try {
      const out = execFileSync(
        'powershell',
        [
          '-NoProfile',
          '-NonInteractive',
          '-Command',
          "Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(Cursor|Code|Windsurf|Trae|codex)$' } | Select-Object -ExpandProperty Path"
        ],
        { encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'ignore'] }
      )
      for (const line of out.split(/\r?\n/)) {
        const p = line.trim()
        if (p) dirs.push(path.dirname(p))
      }
    } catch (e) {}
  }

  // --- Well-known per-user extension roots.
  const home = os.homedir()
  const localAppData = process.env.LOCALAPPDATA || ''
  const appData = process.env.APPDATA || ''
  const candidates = [
    path.join(home, '.cursor', 'extensions'),
    path.join(home, '.vscode', 'extensions'),
    path.join(home, '.vscode-insiders', 'extensions'),
    path.join(home, '.cursor-server', 'extensions'),
    path.join(home, '.vscode-server', 'extensions'),
    path.join(home, '.config', 'Cursor', 'extensions'),
    path.join(home, 'Library', 'Application Support', 'Cursor', 'extensions'),
    localAppData && path.join(localAppData, 'Programs', 'cursor', 'resources', 'app', 'extensions'),
    localAppData && path.join(localAppData, 'Programs', 'Microsoft VS Code', 'resources', 'app', 'extensions'),
    appData && path.join(appData, 'Code', 'extensions')
  ].filter(Boolean)
  dirs.push(...candidates)

  // An install dir can host extensions in a few different layouts.
  const roots = []
  for (const dir of dirs) {
    roots.push(dir)
    // VS Code / Cursor user-installed extensions live next to the install dir.
    roots.push(path.join(dir, 'extensions'))
    // Portable / built-in layout.
    roots.push(path.join(dir, 'resources', 'app', 'extensions'))
    roots.push(path.join(dir, 'data', 'extensions'))
  }

  // De-duplicate while preserving order.
  return [...new Set(roots.map((r) => path.resolve(r)))]
}

function findInExtensionRoot(root) {
  let entries
  try {
    entries = fs.readdirSync(root)
  } catch (e) {
    return null
  }

  const matches = entries
    .filter((name) => EXTENSION_PREFIXES.some((p) => name.startsWith(p)))
    .map((name) => {
      const full = path.join(root, name)
      let mtime = 0
      try {
        mtime = fs.statSync(full).mtimeMs
      } catch (e) {}
      return { full, mtime }
    })
    // Newest extension version wins.
    .sort((a, b) => b.mtime - a.mtime)

  for (const { full } of matches) {
    for (const sub of PLATFORM_SUBPATHS) {
      const candidate = path.join(full, sub)
      if (fs.existsSync(candidate)) return candidate
    }
  }

  return null
}

function resolveCodex() {
  const override = process.env.CODEX_BIN
  if (override) {
    if (fs.existsSync(override)) return override
    console.error('codex-launcher: CODEX_BIN is set but does not exist: ' + override)
    process.exit(1)
  }

  for (const root of editorInstallDirs()) {
    const found = findInExtensionRoot(root)
    if (found) return found
  }

  return null
}

const bin = resolveCodex()

if (!bin) {
  console.error(
    'codex-launcher: could not locate the Codex binary.\n' +
      'Install the Codex / ChatGPT extension in VS Code or Cursor, or set CODEX_BIN\n' +
      'to the full path of the codex executable.\n\n' +
      'Searched extension roots:\n  ' +
      editorInstallDirs().join('\n  ')
  )
  process.exit(1)
}

const args = process.argv.slice(2)

// Diagnostics: set CODEX_LAUNCHER_DEBUG=1 to log the resolved binary to stderr.
// Useful when the MCP server fails to start and the reason is not obvious.
if (process.env.CODEX_LAUNCHER_DEBUG) {
  console.error('codex-launcher: resolved binary = ' + bin)
  console.error('codex-launcher: argv = ' + JSON.stringify(args))
  console.error('codex-launcher: cwd = ' + process.cwd())
}

const child = spawn(bin, args.length > 0 ? args : ['mcp-server'], {
  stdio: 'inherit',
  windowsHide: true
})

child.on('error', (err) => {
  console.error('codex-launcher: failed to start ' + bin + ': ' + err.message)
  process.exit(1)
})

child.on('exit', (code, signal) => {
  if (signal) process.exit(1)
  process.exit(code === null ? 1 : code)
})
