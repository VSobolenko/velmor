// The single definition of the npm package behind each short MCP alias.
//
// `.cursor/mcp.json` names an alias, `.cursor/mcp/run-mcp.cjs` resolves it at launch,
// and the harness sensors (scripts/setup-mcp.mjs, scripts/harness-status.mjs) report
// which package will be installed. All three read this file, so the alias and the
// package it stands for cannot drift apart.
//
// CommonJS on purpose: `run-mcp.cjs` requires it, and an ESM module can import a
// side-effect-free CommonJS module as its default export.

module.exports = Object.freeze({
  context7: '@upstash/context7-mcp',
  'sequential-thinking': '@modelcontextprotocol/server-sequential-thinking',
  playwright: '@playwright/mcp',
  'chrome-devtools': 'chrome-devtools-mcp'
})
