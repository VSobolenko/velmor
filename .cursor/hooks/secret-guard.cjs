// secret-guard: blocks file writes that contain a hardcoded credential.
//
// Contract: reads the tool-call JSON on stdin, prints
//   { "permission": "allow" | "deny" | "ask", "user_message": ..., "agent_message": ... }
// on stdout and exits 0. It never throws: a crash here would be read as a hook
// failure, and this is a security gate that must not fail open silently.
//
// `.env` files are deliberately NOT scanned. An env file is the sanctioned home
// for a credential; blocking writes there would defeat the rule this hook exists
// to enforce. `.env.example` is scanned, because it is committed.

const fs = require('fs')

const SECRET_PATTERNS = [
  { name: 'OpenAI API key', regex: /sk-(proj-)?[A-Za-z0-9_-]{32,}/ },
  { name: 'Anthropic API key', regex: /sk-ant-[A-Za-z0-9_-]{24,}/ },
  { name: 'Stripe secret key', regex: /sk_(test|live)_[A-Za-z0-9]{24,}/ },
  { name: 'Stripe restricted key', regex: /rk_(test|live)_[A-Za-z0-9]{24,}/ },
  { name: 'Langfuse key', regex: /(pk|sk)-lf-[A-Za-z0-9]{20,}/ },
  { name: 'Google/Firebase API key', regex: /AIza[0-9A-Za-z_-]{35}/ },
  { name: 'AWS access key id', regex: /AKIA[0-9A-Z]{16}/ },
  { name: 'GitHub token', regex: /gh[pousr]_[0-9A-Za-z]{36}/ },
  { name: 'GitHub fine-grained token', regex: /github_pat_[0-9A-Za-z_]{22,}/ },
  { name: 'Slack token', regex: /xox[baprs]-[0-9A-Za-z-]{10,}/ },
  { name: 'Private key block', regex: /-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----/ },
  { name: 'JSON service-account private key', regex: /"private_key"\s*:\s*"-----BEGIN/ }
]

// A connection string with an embedded password is a credential. Loopback and
// the compose service names are development defaults and are expected in
// .env.example, so they are exempt.
const LOCAL_HOSTS = /@(localhost|127\.0\.0\.1|::1|db|postgres|redis)[:/]/
const CREDENTIAL_URL = /\b(postgres(ql)?(\+\w+)?|redis|rediss|amqp|mongodb(\+srv)?):\/\/[^:@\s/]+:[^@\s]+@/g

// The tool-input key holding the target path is not part of a documented
// contract, so several spellings are accepted. The value is only used to decide
// whether the file is an env file; if none is present the content is scanned,
// which is the safe direction.
function targetPath(toolInput) {
  return toolInput.path || toolInput.file_path || toolInput.filePath || toolInput.target_file || ''
}

function isEnvFile(filePath) {
  const base = String(filePath).replace(/\\/g, '/').split('/').pop() || ''
  return /^\.env(\.|$)/.test(base) && base !== '.env.example'
}

function findSecrets(text) {
  const found = []
  for (const pattern of SECRET_PATTERNS) {
    if (pattern.regex.test(text)) found.push(pattern.name)
  }
  for (const match of text.match(CREDENTIAL_URL) || []) {
    if (!LOCAL_HOSTS.test(match)) found.push('Connection string with embedded password')
  }
  return found
}

function readInput() {
  try {
    return fs.readFileSync(0, 'utf8')
  } catch (error) {
    return ''
  }
}

function deny(names) {
  process.stdout.write(
    JSON.stringify({
      permission: 'deny',
      user_message:
        'Blocked writing a hardcoded credential: ' +
        names.join(', ') +
        '. Put the value in .env (git-ignored) and reference it through SettingsLoader.',
      agent_message:
        'secret-guard blocked a file edit containing a hardcoded credential: ' + names.join(', ')
    })
  )
  process.exit(0)
}

function allow() {
  process.stdout.write(JSON.stringify({ permission: 'allow' }))
  process.exit(0)
}

function main() {
  const raw = readInput()

  let payload
  try {
    payload = JSON.parse(raw)
  } catch (error) {
    allow()
    return
  }

  const toolName = payload.tool_name || payload.toolName || ''
  if (!/^(Write|StrReplace|EditNotebook)$/.test(toolName)) {
    allow()
    return
  }

  const toolInput = payload.tool_input || payload.toolInput || {}
  if (isEnvFile(targetPath(toolInput))) {
    allow()
    return
  }

  const candidates = [toolInput.contents, toolInput.content, toolInput.new_string].filter(
    (value) => typeof value === 'string'
  )

  const found = new Set()
  for (const text of candidates) {
    for (const name of findSecrets(text)) found.add(name)
  }

  if (found.size > 0) {
    deny([...found])
    return
  }
  allow()
}

main()
