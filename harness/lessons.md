# Harness lessons (factory memory)

Append-only. Never edit an entry to correct it; append a new one that says what changed.
Read at session start by `.cursor/hooks/session-start.cjs`.

The question an entry answers is not "what broke" but "what will prevent this class of
defect the next time", so the fix class matters more than the narrative.

## Template

```
### YYYY-MM-DD - short title
- Symptom:
- Root cause:
- Fix class: (AGENTS.md | hook | sensor | skill | rule | spec | script)
- Evidence:
- Change made:
```

---

### 2026-09-23 - the harness was built surface by surface, and never checked as a whole

- Symptom: the repository had rules, commands, five hooks and a Codex MCP server, and still
  no way to answer "is the harness complete and consistent". Specifically: no project
  subagents; long Codex work could only travel over a transport with an MCP timeout; no
  `.cursorignore`; no mirroring of agent definitions for the Claude and Codex runtimes; and
  the Codex channel had no durable worker ledger. Two constraints existed as prose with no
  mechanism: "never combine `danger-full-access` with `approval-policy: never`", and the
  assumption that every script named in `hooks.json` still exists.
- Root cause: each surface was added when a need appeared, and nothing ever asked whether
  the set was complete or internally consistent. This class of defect is invisible at the
  moment it appears - a renamed hook script, a subagent missing from a mirror, and an MCP
  alias absent from the table all produce no error until much later, when an agent quietly
  stops being governed.
- Fix class: sensor + hook + AGENTS.md.
- Evidence: `node scripts/harness-status.mjs` reported `NOT READY` against the incomplete
  harness; after the work it reports the same checks as `PASS`. The sensor was proved able
  to fail by running it against a tree with an injected defect (see `scripts/selftest.mjs`).
- Change made:
  - `scripts/harness-status.mjs` - one sensor for surfaces, subagent mirror parity, hook
    wiring, MCP alias resolution, the Codex channel, `.velmor/` being ignored, and OpenSpec
    change integrity. `FAIL` exits non-zero; `WARN` distinguishes a machine-level gap from a
    repository defect.
  - `scripts/selftest.mjs` - drives the harness scripts against injected defects, so the
    sensors are themselves tested.
  - `scripts/codex-run.mjs` plus `harness/codex-workers.md` and `harness/dual-agent.md` - a
    durable worker channel with a ledger and resume-by-session-id, replacing long work over
    the MCP transport.
  - `.cursor/agents/*.md` - six project subagents, mirrored into `.claude/agents/` and
    `.codex/agents/`.
  - `.cursor/hooks/mcp-audit.cjs` - turns the `danger-full-access` + `approval-policy: never`
    rule into an enforcement, on the one event where it is a decision rather than a sentence.
  - `.cursor/hooks/session-start.cjs`, `after-file-edit.cjs`, `stop-gate.cjs` and
    `.cursor/rules/08-evidence-and-sensors.mdc` - the loop that keeps the harness in view:
    what it knows at start, what it touched, and one ask for evidence at the end.

### 2026-09-23 - a full-access worker is refused by the runner, not warned about

- Symptom: the peer protocol said "`danger-full-access` should not be used unless the task
  explicitly requires and authorizes it", which is a warning in a document, and a durable
  unattended worker is exactly the context where an unrestricted agent is most dangerous.
- Root cause: a documented warning and an enforced boundary were treated as the same thing.
- Fix class: script.
- Evidence: `node scripts/codex-run.mjs run --id probe --sandbox danger-full-access
  --prompt-file <file>` exits 1 with the refusal and starts no worker.
- Change made: the runner accepts only `read-only` and `workspace-write`. Full access stays
  available through the MCP tool, where `mcp-audit.cjs` denies the combination that removes
  the human from the loop.

### 2026-09-23 - the edit ledger wrote Windows separators, and the sensor that caught it greped a file instead of reading it

- Symptom: `scripts/selftest.mjs` failed twice on its first run, on two unrelated checks.
  (1) The edit ledger recorded `packages\core\src\x.py`, so a ledger written on Windows did
  not read the same as one written on macOS or Linux. (2) The check for MCP alias drift
  reported two aliases as missing from `mcp-aliases.cjs` that were present in it.
- Root cause: two different mistakes with the same shape - working from a copy of the truth
  rather than the truth. (1) `after-file-edit.cjs` used `path.relative()` and wrote its
  platform output straight into the ledger, so a repository-relative path was not
  repository-style. (2) The alias check searched the *text* of `mcp-aliases.cjs` for
  `<alias>:`, which misses a quoted key (`'sequential-thinking':`) and would have accepted a
  name that appeared only in a comment. The second is the worse defect: a sensor with a
  false positive gets "fixed" by relaxing the sensor.
- Fix class: script + sensor.
- Evidence: `node scripts/selftest.mjs` reported
  `FAIL records the edited path relative to the workspace root - "...packages\\core\\src\\x.py"`
  and `FAIL every run-mcp alias in mcp.json exists in the alias table`, naming
  `sequential-thinking` and `chrome-devtools`. After both fixes it reports `VERDICT: PASS`.
- Change made: `after-file-edit.cjs` normalises the relative path to forward slashes;
  `selftest.mjs` imports the alias table and uses `hasOwnProperty` instead of reading the
  file as text.

### 2026-09-23 - Codex worker prompts were documented under a path the agent cannot write

- Symptom: the documented workflow was `--prompt-file .velmor/codex/prompts/<file>.md`, and
  every attempt to create that file returned "Read permission denied". `codex-run.mjs` had
  been written, documented and shipped without a single worker ever being started, so nothing
  revealed that the workflow could not be executed at all.
- Root cause: `.velmor/` is listed in `.cursorignore`, which is what keeps harness scratch
  state out of the agent's index - and Cursor denies an agent read and write on an ignored
  path, not merely indexing. The ledger belongs there; the prompts do not. A prompt is the
  task statement a reviewer judges a worker's diff against, so it belongs in the diff.
- Fix class: script + sensor.
- Evidence: `Write` to `.velmor/codex/prompts/smoke.md` returned `Read permission denied`,
  twice, before and after the directory existed. After moving the convention,
  `harness/codex/prompts/smoke-test.md` was written normally and the worker ran.
- Change made: prompts live in `harness/codex/prompts/` and are tracked; the ledger stays in
  `.velmor/codex/`. `harness/codex/prompts/README.md` carries the template,
  `smoke-test.md` is the read-only prompt that proves the channel, and both are in
  `REQUIRED_FILES` so `harness-status.mjs` fails if the convention is lost.

### 2026-09-23 - resuming a read-only worker silently gave it write access

- Symptom: `codex-run.mjs resume` on a worker started with `--sandbox read-only` produced a
  turn that ran with `workspace-write` and `approval: never`. A Verify worker, whose whole
  purpose is to read and report without touching anything, could be escalated to a writer by
  a resume.
- Root cause: `codex exec resume` accepts neither `--sandbox` nor `--cd`, and the runner's
  comment assumed "the resumed turn inherits the sandbox and the root recorded when the
  session started". The root is inherited, because it is part of the recorded session. The
  sandbox is not: it falls back to the CLI default. The assumption had never been tested, and
  the runner had never been run.
- Fix class: script + AGENTS.md.
- Evidence: Codex prints the effective policy as `sandbox: ...` in its start banner. The
  ledger for worker `smoke` contains, in order, `sandbox: read-only` (the run),
  `sandbox: workspace-write [workdir, /tmp, $TMPDIR]` (the resume, before the fix), and
  `sandbox: read-only` (the resume, after it). `codex exec resume --help` confirms there is no
  `-s/--sandbox`; `-c sandbox_mode=read-only` was tested on its own and produces
  `sandbox: read-only`.
- Change made: `resume` always passes `-c sandbox_mode="${meta.sandbox}"`, replaying the
  sandbox the worker was started with, and `harness/codex-workers.md` records the real
  behaviour instead of the assumption.

### 2026-09-23 - a colon inside a YAML list item silently disabled the whole OpenSpec contract

- Symptom: an edit to `openspec/config.yaml` produced a warning from `openspec validate` -
  "could not parse ... (Implicit keys need to be on a single line at line 159, column 9:);
  ignoring it" - and then reported the change as **valid**, exiting 0. Nothing failed. The
  project context and every rule the proposal/spec/design/tasks writers are meant to follow
  had stopped being loaded, and the only signal was a warning on a command whose exit code
  says success.
- Root cause: `openspec/config.yaml` mixes block scalars (`context: |`), where a colon is
  ordinary text, with plain multi-line list scalars under `rules:` and `operations:`, where a
  continuation line containing `key: ` is an implicit key and a parse error. The two shapes
  sit a few lines apart and look alike. The failure is invisible by design: OpenSpec degrades
  rather than erroring, because a missing config is legitimate for a repo that has not
  configured one.
- Fix class: sensor.
- Evidence: with the broken file, `openspec validate --strict redesign-storefront-ux` printed
  the parse warning twice and then `Change 'redesign-storefront-ux' is valid`, exiting 0. A
  second injection - `- A plain scalar, first line` / `  output: a colon here breaks the parse`
  - reproduces it at line 4, and after the sensor was added the injected-defect run reports
  `FAIL OpenSpec is ignoring part of openspec/config.yaml: Warning: could not parse ...`.
- Change made: `harness-status.mjs` runs `openspec validate --strict --all` and FAILs when the
  output contains `could not parse`, `ignoring this artifact` or `ignoring it`, instead of
  trusting the exit code. `scripts/selftest.mjs` injects a config that cannot be read and
  asserts the FAIL, so the sensor is proven rather than assumed. The real repo reports
  `Totals: 10 passed, 0 failed (10 items)`.

### 2026-09-23 - the subagent mirror was a manual copy step

- Symptom: the six project subagents were copied into `.claude/agents/` and `.codex/agents/`
  by hand, so the three copies were correct exactly once. `harness-status.mjs` could detect
  drift but nothing could fix it, which means the only way to satisfy the sensor was to copy
  files manually - the step that caused the drift.
- Root cause: a sensor without a remediation path is a nag. Detection is the cheaper half of
  the problem; if the fix is a manual procedure, the drift returns with the next edit.
- Fix class: script + sensor.
- Evidence: injecting both drift modes - a modified `.codex/agents/evaluator.md` and a stale
  `.claude/agents/ghost.md` - made `sync-agents.mjs --check` report
  `.codex/agents/evaluator.md: differs` and `.claude/agents/ghost.md: stale, not in
  .cursor/agents/` and exit 1; the sync repaired both and a second check reported
  `6 subagents mirrored in 2 runtimes; in sync`.
- Change made: `scripts/sync-agents.mjs` treats `.cursor/agents/` as the source, copies into
  both mirrors, and deletes files a mirror holds that the source no longer does - a retired
  subagent left behind is still loadable, so it is drift too. `--check` makes it usable as a
  gate, which `scripts/selftest.mjs` now runs on every self-test.

### 2026-09-23 - a successful worker was reported as AUTH_ERROR because a lint rule contains "401"

- Symptom: the first real `resume` run exited 0 and produced a correct answer, and the runner
  printed `codex-run: smoke exit=0 signal=AUTH_ERROR`.
- Root cause: two mistakes. The classifier ran on **every** finish, including a success, so
  there was a signal to be wrong about at all; and its AUTH pattern included a bare `401`,
  which matched the ruff rule code `F401` inside `pyproject.toml` - a file the worker had
  merely read. A substring is not a signal.
- Fix class: script + sensor.
- Evidence: scanning `.velmor/codex/smoke.err` for the old pattern returned exactly two lines,
  both `"F401",`. After the fix, `signal` is `null` on the exit record of a successful run.
- Change made: a signal is attached only to a non-zero exit, `401` requires its HTTP context
  (`http 401`, `status code 401`), and the patterns moved to `scripts/lib/codex-signals.mjs`
  so `scripts/selftest.mjs` can assert them directly - including the `"F401",` line as a
  regression case - instead of the only test being a model call.

### 2026-09-23 - `.cursorignore` cannot be created or written by the agent write tool

- Symptom: every attempt to write `.cursorignore` returned "Write permission denied", on a
  file that did not exist and in a directory the shell could write to without complaint.
  This was reported as a blocker in an earlier session and left undone, so
  `harness-status.mjs` failed on `.cursorignore` and the harness stayed `NOT READY`.
- Root cause: Cursor treats `.cursorignore` as a protected file, because writing it changes
  the agent's own index. The denial is at the tool layer, not the filesystem: `New-Item`
  through the shell creates it immediately, and the same write tool then still refuses to
  fill it.
- Fix class: sensor + AGENTS.md.
- Evidence: `Write` returned `Write permission denied: ` twice, before and after the file
  existed; `New-Item -ItemType File -Path .cursorignore` then `Set-Content` succeeded, and
  `node scripts/harness-status.mjs` moved from `FAIL .cursorignore` to `PASS`.
- Change made: the file is written through the shell. An agent that hits this must not read
  it as a permissions problem on the machine and abandon the file - use the shell and move
  on. This entry is the record, so the loop is not repeated a third time.

### 2026-09-23 - the Codex-first requirement had no enforcement, and `/ship` implemented in Cursor

- Symptom: the user ran the autonomous loop, and the agent implemented the work itself while
  Codex sat idle. Nothing failed. `harness-status.mjs` said READY, `selftest.mjs` passed, the
  hooks all behaved, and the previous session had reported the harness as complete.
- Root cause: two layers of prose and no mechanism. `AGENTS.md` listed Codex as one optional
  row in a role table, and `/ship` step 1 instructed the orchestrator to "dispatch ONE fresh
  implementer subagent" - which is Cursor. So the documented default was Codex and the
  documented procedure was Cursor, and only one of them was executable. A rule that cannot
  fail is not a rule; this file already carried that lesson, and the very next change broke it.
  The deeper cause of the report being wrong: "the harness is complete" was checked against a
  file inventory, and a file inventory cannot see that a requirement has no enforcement.
- Fix class: hook + command + rule + sensor.
- Evidence: `node scripts/selftest.mjs`, section `codex-gate`, 9 checks passing, and it asserts
  both directions rather than only the deny half:
  `PASS denies product code with no worker behind it - deny`,
  `PASS never gates the verdict path`,
  `PASS never gates the harness itself`,
  `PASS allows product code once a worker is recorded in this session - allow`,
  `PASS a worker from before this session does not satisfy the gate - deny`.
  `node scripts/harness-status.mjs` gained
  `PASS preToolUse wires codex-gate.cjs: product code needs a Codex worker behind it`.
- Change made: `codex-gate.cjs` refuses a write to `packages/`, `velmor/` or `storefront/`
  unless the worker ledger holds a worker for this session; the verdict path and the harness
  are excluded by name, because delegating those would be wrong rather than merely
  unnecessary; `VELMOR_CODEX_GATE=off` is the documented door for a real exception; `/ship`
  step 1 starts a worker, names the fallback rungs and reports who implemented; `session-start`
  stamps `.velmor/session/epoch` so "this session" is decidable; `AGENTS.md` carries the rule
  as rule 1 of four, which is the only channel Codex itself reads.
- Residual, and it is not closed by this hook: hooks intercept Cursor tool calls, so a worker's
  own edit is invisible to `secret-guard` and `ui-guard`. The compensating control is a manual
  one - the orchestrator reads the diff and runs the locale parity check for `storefront/**`,
  and `/ux-verify` before completion. A mechanical sensor for a worker's diff is still missing.

### 2026-09-23 - every hook was inert: the payload arrives with a UTF-8 BOM

- Symptom: the edit ledger recorded one line per edit with an **empty path** and no conversation
  id, for every edit by every session. Separately, a `Write` payload containing a hardcoded live
  Stripe key passed `secret-guard.cjs`, which answered `{"permission":"allow"}`.
- Root cause: Cursor writes hook input to stdin as UTF-8 **with a byte-order mark**, and
  `JSON.parse` rejects a leading U+FEFF. Every hook read stdin with
  `JSON.parse(fs.readFileSync(0, 'utf8'))` inside a `try` that fell back to `{}`, and `{}` is a
  perfectly valid "no payload" input - so each hook took its empty-input branch and reported
  success. Measured: `firstBytesHex efbbbf7b22636f6e766572736174`, `indexOfBrace 1`,
  `parseError "Unexpected token ..., is not valid JSON"`.
  The reason it survived review is the more important half: `scripts/selftest.mjs` fed every hook
  clean JSON with no BOM - a payload the runtime never sends - so the suite asserted against an
  imagined input and certified a path that does not execute. A sensor tested against an imagined
  payload is not a sensor.
- Fix class: shared module + sensor + hook.
- Evidence: a probe spawning `secret-guard.cjs` twice with the same Stripe payload returned
  `no BOM -> {"permission":"deny"}` and `with BOM -> {"permission":"allow"}`. After the fix the
  ledger records
  `2026-09-23T17:26:44.113Z  1bc5218d-e287-42e5-8e4e-3aaf9f50be47  scripts/selftest.mjs`
  where the three fields before were `-` and empty, and `selftest.mjs` passes with the BOM sent
  to all eleven hooks.
- Change made: `.cursor/hooks/lib/hook-io.cjs` reads stdin with the BOM stripped, reports a parse
  failure on stderr instead of swallowing it, and normalises the workspace root; all eleven hooks
  delegate to it; `runHook` in the selftest now prefixes the BOM, so every hook assertion is about
  the real payload and a regression fails the suite rather than hiding.
- Second defect this unmasked: the same payload carries `workspace_roots: ["/d:/Python/Velmor"]`,
  a URL-ish form, and `path.join('/d:/Python/Velmor', '.velmor')` resolves to
  `D:\d:\Python\Velmor\.velmor` - a real directory on the drive root, not the workspace. With the
  BOM fixed and this not fixed, the ledger would have started writing somewhere plausible and
  wrong. `workspaceRoot()` handles it.
- Third defect this exposed: `scripts/selftest.mjs` contained a literal `sk_live_...` test
  fixture, and the guard scans the content being written - so the fixture made the file that tests
  the guard uneditable by the guard. The fixture is now assembled at runtime; the payload the hook
  receives is unchanged, so the test still tests what it claims.

### 2026-09-23 - two agents in one working tree, and no way to see it

- Symptom: `uv run python -m pytest packages velmor -q` reported `14 failed, 669 passed`, with
  every failure in `packages/services/tests/unit/commerce/test_curation.py`. Three minutes later
  the same command reported `689 passed`. The same file collected 27 tests in one run and 33 in
  the next.
- Root cause: a second agent session was writing product code in the same directory while the
  tests ran. `packages/services/src/commerce/curation.py` was modified at 20:20:42, one minute
  before the check, and the file under test at 20:18:23. `harness/dual-agent.md` already said two
  writers on one tree is a defect waiting to happen, and nothing could detect it - so the
  documented rule produced no signal, and a flaky number was nearly reported as a result.
- Fix class: sensor.
- Evidence: `node scripts/harness-status.mjs` now reports
  `WARN  2 sessions edited files in the last 30 minutes: 1bc5218d (4 files), fc2f59b1 (1 files).`
  The same run passes with a single writer. The conversation ids come from the edit ledger and
  became readable only once the BOM defect above was fixed - the two findings are one root cause
  apart.
- Change made: a `Concurrent writers` section in `harness-status.mjs` reads the edit ledger for
  the last 30 minutes, groups edits by conversation id and warns when more than one session has
  written. It is a warning and not a block: overlapping sessions are sometimes deliberate.

### 2026-09-23 - the secret-guard exemption for a loopback DSN could never fire

- Symptom: `StrReplace` on `packages/api/.env.example` was denied with "Blocked writing a
  hardcoded credential: Connection string with embedded password", for an edit that changed one
  currency value and touched no credential. The same denial hit
  `packages/api/tests/unit/configs/test_settings.py`. Driving the hook directly confirmed it: a
  loopback DSN and even a `@db:` DSN - the compose service name the hook's own comment names as
  exempt - were both denied.
- Root cause: `CREDENTIAL_URL` stopped at the `@`, so the text it matched held the scheme and the
  userinfo and no host at all. `LOCAL_HOSTS` was then tested against that host-less string, so the
  exemption the hook documents was unreachable code. The guard therefore denied every write to
  any file holding a development DSN, and because it scans the whole content being written, those
  files became uneditable - while `.env.example` is required to contain a DSN.
- Fix class: hook + sensor.
- Evidence: before the fix, a `@db:5432` DSN -> `deny`; after it, `localhost`, `db` and `redis` ->
  `allow` while `prod.example.com` and the lookalike `localhost.evil.com` -> `deny`. Injecting the
  old pattern back made the two new selftest checks report
  `FAIL   allows a loopback DSN - the exemption the hook documents - deny`; restoring it returned
  `VERDICT: PASS`.
- Change made: the host is now part of `CREDENTIAL_URL`, and `LOCAL_HOSTS` accepts the end of the
  match as well as a separator, so the exemption fires and still cannot be fooled by a host that
  merely starts with `localhost`. `scripts/selftest.mjs` asserts both directions, with the
  fixtures assembled at runtime for the reason recorded in the entry above.
- Footnote on the same defect: a first draft of this entry was denied as well, because it quoted
  the matched fragment verbatim. The guard scans prose as readily as code, so a lesson about a
  false positive is itself a false positive unless the fragment is described rather than copied.
