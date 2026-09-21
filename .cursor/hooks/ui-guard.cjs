// ui-guard: blocks edits that hardcode a language or a buyer-facing string into
// the storefront.
//
// Why this exists rather than a line in a rule file:
//
//   The storefront once shipped with `copy.ts` - one Belarusian module imported
//   by every component - and `<html lang="be">` fixed in the root layout. Every
//   string was correct and the shop was unusable for anyone who does not read
//   Belarusian. That is a diff that looks like a feature.
//
//   `.cursor/rules/07-product-surface.mdc` states the rule. This hook is the part
//   of it a machine can decide without judgement: a Cyrillic literal in a
//   component is buyer-visible copy that must live in a dictionary, and a quoted
//   locale in `lang=` is a language chosen by a developer for everyone.
//
// What it deliberately does NOT catch, because a false positive here costs more
// than the miss:
//
//   - an English literal that is buyer-visible ("Add to cart"). Telling a label
//     from a class name or an API path needs judgement, so that is the checklist
//     in `.cursor/skills/storefront-ux/SKILL.md` and `/ux-verify`, not this hook.
//   - a missing translation key. `storefront/scripts/check-i18n.mjs` owns parity
//     across the locale files and runs before the build.
//
// Scope: `storefront/src/**` `.ts` and `.tsx` only. Everything under
// `src/lib/i18n/` is exempt, including the module - that directory is the
// sanctioned home for locale data, and the display names of the languages
// themselves ("Русский", "Беларуская", "English") are legitimately Cyrillic
// literals there. The rule this hook enforces is that copy does not live in a
// component or a page, which is where it lived when this failed.
//
// Contract: tool-call JSON on stdin, permission JSON on stdout, exit 0. It never
// throws - a crashed hook is read as a hook failure, and this gate must not fail
// open in silence - so every unexpected path allows and exits.

const fs = require('fs')

const CYRILLIC = /[\u0400-\u04FF]/
const LOCALES = /(ru|be|en)/

// A literal locale in an `lang=` or in a default-locale constant. `lang={locale}`
// is the correct form and does not match.
const HARDCODED_LANG = /lang\s*=\s*["'](ru|be|en)["']/i
const HARDCODED_DEFAULT = /\b(defaultLocale|DEFAULT_LOCALE)\b\s*[:=]\s*["'](ru|be|en)["']/

// Attributes whose value a buyer or a screen reader reads. A non-empty literal
// with a letter in it is copy.
const COPY_ATTRIBUTES = /\b(aria-label|placeholder|alt|title)\s*=\s*["']([^"']*[A-Za-z\u0400-\u04FF][^"']*)["']/g

// A literal passed to a matching method is a pattern, not copy. Found in practice:
// `lib/brand.ts` matches Cyrillic slugs with `.includes("ілюстр")`, and flagging that
// would be a false positive that trains an implementer to bypass the hook. The hook
// is a net, not a parser; a literal assembled across lines still gets flagged.
const MATCHING_CALL =
  /\.(?:includes|startsWith|endsWith|indexOf|lastIndexOf|match|matchAll|search|localeCompare|replace|replaceAll)\s*\(\s*["'`][^"'`]*["'`]/g

// A character class or a codepoint escape naming a script is likewise a pattern.
const SCRIPT_PATTERN = /\\p\{Script=[A-Za-z]+\}/g

function readInput() {
  try {
    return fs.readFileSync(0, 'utf8')
  } catch (error) {
    return ''
  }
}

function targetPath(toolInput) {
  return toolInput.path || toolInput.file_path || toolInput.filePath || toolInput.target_file || ''
}

function normalise(filePath) {
  return String(filePath).replace(/\\/g, '/').replace(/^\.\//, '')
}

// The storesfront's own sources, excluding anything that is not a component or a
// module. Tests and build scripts are exempt: a test asserting that a locale file
// contains a translation legitimately names one.
function isGuardedSource(candidate) {
  if (!candidate.startsWith('storefront/src/')) return false
  if (!/\.(ts|tsx)$/.test(candidate)) return false
  if (candidate.includes('/lib/i18n/')) return false
  if (/\.(test|spec)\.tsx?$/.test(candidate)) return false
  return true
}

// Strip block comments and line-comment tails so a comment is not mistaken for
// copy. A `//` preceded by `:` is left alone, because that is a URL scheme.
function withoutComments(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1 ')
}

// Remove the patterns named above so a matching literal is not read as copy. The
// attribute scan runs on the result, so a literal `alt="..."` is still caught.
function withoutPatterns(text) {
  return text.replace(MATCHING_CALL, ' ').replace(SCRIPT_PATTERN, ' ')
}

function violations(text, candidate) {
  const found = []
  const code = withoutPatterns(withoutComments(text))

  if (CYRILLIC.test(code)) {
    found.push(
      'Cyrillic text in ' +
        candidate +
        '. Buyer-visible copy must come from storefront/src/lib/i18n/*.json'
    )
  }
  if (HARDCODED_LANG.test(code)) {
    found.push(
      'A literal language in lang= in ' + candidate + '. Set it from the resolved locale'
    )
  }
  if (HARDCODED_DEFAULT.test(code)) {
    found.push(
      'A hardcoded default locale in ' +
        candidate +
        '. The default lives in the i18n module only'
    )
  }

  COPY_ATTRIBUTES.lastIndex = 0
  let match
  while ((match = COPY_ATTRIBUTES.exec(code)) !== null) {
    if (CYRILLIC.test(match[2])) continue
    found.push(
      'A literal ' +
        match[1] +
        '="' +
        match[2] +
        '" in ' +
        candidate +
        '. It is read by a buyer or a screen reader, so it belongs in the dictionaries'
    )
  }

  return found
}

function deny(entries) {
  process.stdout.write(
    JSON.stringify({
      permission: 'deny',
      user_message:
        'ui-guard blocked a storefront edit that hardcodes buyer-facing copy or a language:\n' +
        entries.map((entry) => '  - ' + entry).join('\n') +
        '\nSee .cursor/rules/07-product-surface.mdc.',
      agent_message:
        'ui-guard denied this edit. Fix it this way and retry:\n' +
        entries.map((entry) => '  - ' + entry).join('\n') +
        '\nMove the string into storefront/src/lib/i18n/{ru,be,en}.json and read it ' +
        'through dictionaryFor(locale). Set lang from the resolved locale. Do not ' +
        'widen the hook or bypass it; if it is a false positive, say so and ask the human.'
    })
  )
  process.exit(0)
}

function allow() {
  process.stdout.write(JSON.stringify({ permission: 'allow' }))
  process.exit(0)
}

function main() {
  let payload
  try {
    payload = JSON.parse(readInput())
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
  const candidate = normalise(targetPath(toolInput))
  if (!isGuardedSource(candidate)) {
    allow()
    return
  }

  const bodies = [toolInput.contents, toolInput.content, toolInput.new_string].filter(
    (value) => typeof value === 'string'
  )

  const found = new Set()
  for (const body of bodies) {
    for (const entry of violations(body, candidate)) found.add(entry)
  }

  if (found.size > 0) {
    deny([...found])
    return
  }
  allow()
}

main()
