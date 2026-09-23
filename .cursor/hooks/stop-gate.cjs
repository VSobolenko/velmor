#!/usr/bin/env node
/**
 * stop - one evidence follow-up when a session ends without proof.
 *
 * Why this exists
 * ---------------
 * The most expensive failure in this repository is not a wrong edit, it is a confident
 * "done" with nothing behind it. The storefront once shipped as a list of filenames
 * while every gate passed, and the reason no gate caught it is that no gate looked at a
 * rendered page.
 *
 * This is back-pressure, not a blocker: on the first stop of a completed session it
 * submits one follow-up asking for the evidence. `loop_limit: 1` in hooks.json and the
 * `loop_count === 0` check below mean it cannot loop, so it costs one turn at most.
 *
 * It deliberately does not attempt to verify anything itself. A hook cannot tell whether
 * the session needed a rights check, and a hook that guesses would either nag on trivial
 * turns or fire on nothing; the honest division is that the hook asks, and the agent
 * answers with output.
 *
 * `VELMOR_STOP_FOLLOWUP=0` disables it.
 *
 * Contract: stop input JSON on stdin, `{ followup_message }` or `{}` on stdout, exit 0.
 */

const hookIo = require('./lib/hook-io.cjs')

function main() {
  if (process.env.VELMOR_STOP_FOLLOWUP === '0') {
    process.stdout.write('{}')
    return
  }

  const input = hookIo.readPayload()

  const status = input.status || 'completed'
  const loopCount = Number(input.loop_count || 0)

  if (status !== 'completed' || loopCount !== 0) {
    process.stdout.write('{}')
    return
  }

  process.stdout.write(
    JSON.stringify({
      followup_message:
        'Velmor stop gate. Before this session ends, state the evidence for what changed, ' +
        'or say plainly that it is unverified.\n' +
        '- Python changed: paste the key line of `uv run ruff check` and ' +
        '`uv run python -m pytest packages velmor -q`.\n' +
        '- Rights, screening, connectors or the gate changed: `/rights-verify` is required.\n' +
        '- Anything a buyer reads or acts on changed: `/ux-verify` is required, and its ' +
        'screenshots are the evidence - a green suite is not.\n' +
        '- Harness files changed: `node scripts/harness-status.mjs`.\n' +
        'If there was nothing to verify, reply DONE with one line saying so.'
    })
  )
}

main()
