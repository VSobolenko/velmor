// destructive-guard: blocks irreversible commands before they run.
//
// No matcher is configured for this hook, on purpose. A matcher like `git|docker`
// would miss `Remove-Item -Recurse` and `docker-compose` written without the
// subcommand, and a guard that misses is worse than a guard that costs 40ms of
// node startup. The script is the filter.
//
// This is NOT fail-closed: if node itself is broken, blocking every shell command
// would brick the session, and the user could not even run `git status` to see
// why. The script is written to never throw.
//
// Contract: { "command": ... } on stdin, permission JSON on stdout, exit 0.

const fs = require('fs')

const RULES = [
  {
    // Force-pushing a protected branch rewrites shared history.
    test: (c) =>
      /\bgit\b/.test(c) &&
      /\bpush\b/.test(c) &&
      /(--force\b|--force-with-lease|-f\b)/.test(c) &&
      /\b(main|master)\b/.test(c),
    reason: 'force-pushing to main/master rewrites shared history',
    hint: 'Open a pull request instead. If history genuinely must be rewritten, run it yourself.'
  },
  {
    test: (c) => /\bgit\b/.test(c) && /\breset\s+--hard\b/.test(c),
    reason: 'git reset --hard discards uncommitted work irrecoverably',
    hint: 'Use `git stash` or commit first.'
  },
  {
    test: (c) => /\bgit\b/.test(c) && /\bclean\s+-[a-z]*[fd]/.test(c),
    reason: 'git clean deletes untracked files irrecoverably',
    hint: 'List them with `git clean -n` first, then delete what you actually meant to.'
  },
  {
    test: (c) => /\bgit\b/.test(c) && /\b(filter-branch|filter-repo)\b/.test(c),
    reason: 'history rewriting is not allowed by rule',
    hint: 'Do not rewrite git history (see .cursor/rules/01-security-secrets.mdc).'
  },
  {
    test: (c) => /\bdocker\b/.test(c) && /\b(down|rm)\b/.test(c) && /(-v\b|--volumes\b)/.test(c),
    reason: 'removing docker volumes deletes the local Postgres and Redis data irrecoverably',
    hint: 'Run `docker compose down` without -v, or rebuild the data from a seed.'
  },
  {
    test: (c) => /\bdocker\b/.test(c) && /\bvolume\s+(rm|prune)\b/.test(c),
    reason: 'volumes hold the only copy of the local database',
    hint: 'Ask the user to run it if the volume really must go.'
  },
  {
    test: (c) => /\b(dropdb|drop\s+database)\b/i.test(c),
    reason: 'dropping the database is irreversible',
    hint: 'Create a scratch database instead of dropping the working one.'
  },
  {
    // Covers PowerShell and POSIX recursive force deletion of a broad path.
    test: (c) =>
      /(Remove-Item|rm|del|rd|rmdir)\b[^\n]*\b(-Recurse\b|-r\b|-rf\b|--recursive)/.test(c) &&
      /(\s|["'=])(\/|\\)?(\*|\.\.?\/?)?\s*$|\s(\/|~|C:\\|\$HOME|\$env:USERPROFILE)\s*$/.test(c),
    reason: 'recursive force deletion of a broad path',
    hint: 'Name the exact directory you intend to delete.'
  }
]

function readInput() {
  try {
    return fs.readFileSync(0, 'utf8')
  } catch (error) {
    return ''
  }
}

function allow() {
  process.stdout.write(JSON.stringify({ permission: 'allow' }))
  process.exit(0)
}

function main() {
  const raw = readInput()

  let command = raw
  try {
    const payload = JSON.parse(raw)
    command = payload.command || payload.shell_command || raw
  } catch (error) {
    command = raw
  }

  const candidate = String(command).trim()
  if (candidate === '') {
    allow()
    return
  }

  const matched = RULES.find((rule) => rule.test(candidate))
  if (matched) {
    process.stdout.write(
      JSON.stringify({
        permission: 'deny',
        user_message:
          'Blocked: ' + matched.reason + '.\n\n  ' + candidate + '\n\n' + matched.hint,
        agent_message:
          'destructive-guard blocked a destructive command (' +
          matched.reason +
          '). Do not work around it; ask the user to run it if it is genuinely required.'
      })
    )
    process.exit(0)
  }

  allow()
}

main()
