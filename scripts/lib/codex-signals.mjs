#!/usr/bin/env node
/**
 * Codex failure signals.
 *
 * Why this is its own module
 * --------------------------
 * This classifier decides which writer runs next: a signal selects a rung of the fallback
 * ladder in `harness/dual-agent.md`, and a wrong one either discards work that succeeded or
 * retries a path that is broken. Two things follow, and both are why it is not a private
 * function inside `codex-run.mjs`:
 *
 *   1. It is a pure function of text, so it can be tested directly. Testing it through a
 *      real worker costs a model call per case; testing it here costs nothing.
 *   2. `scripts/selftest.mjs` and `codex-run.mjs` must agree on the patterns, so the
 *      definition lives in exactly one place.
 *
 * Precision, not recall
 * ---------------------
 * A false positive is worse than a miss. A miss falls through to the generic "retry once,
 * then switch writers" path, which is cheap and bounded. A false positive sends an
 * orchestrator to a different agent for a failure that never happened, and it discards the
 * evidence that the task was fine.
 *
 * The regression that forced this file: the AUTH pattern was a bare `401`, a worker read
 * `pyproject.toml`, the text contained the ruff rule code `F401`, and a completed run was
 * reported as `AUTH_ERROR`. A bare number is never a signal; it needs its HTTP context.
 */

/**
 * Ordered. The first match wins, so a rate limit is reported as one even when the same
 * output also contains a token-limit warning it caused.
 */
export const FAILURE_SIGNALS = [
  {
    signal: 'RATE_LIMITED',
    pattern: /usage limit|rate limit|429|too many requests|quota exceeded|limit reached/
  },
  {
    signal: 'CONTEXT_LIMIT',
    pattern: /context (window|length)|too many tokens|token limit|compact/
  },
  {
    signal: 'AUTH_ERROR',
    pattern:
      /not logged in|codex login|invalid api key|invalid_api_key|refresh token|unauthorized|authentication (failed|error)|(?:http|status)(?: code)?[:\s]+401\b/
  }
]

/**
 * The failure signal in a block of output, or `null` when nothing matches.
 *
 * Call this on failures only. A successful run has no failure to classify, and classifying
 * one is how a `DONE` worker gets a signal attached to it.
 */
export function classifyFailure(text) {
  const haystack = String(text || '').toLowerCase()
  if (!haystack) return null
  for (const { signal, pattern } of FAILURE_SIGNALS) {
    if (pattern.test(haystack)) return signal
  }
  return null
}
