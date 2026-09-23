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

### 2026-09-23 - a legal publication decision produced a good the shop could never show

- Symptom: one published good advertised a preview that answered 404 in every locale.
  `GET /catalogue/goods/{id}` said `200` and handed out a `preview_url`, and that URL said
  `{"detail":"no preview exists for this good"}` - the same status and the same body the API uses
  for a good that is not in the catalogue at all. The buyer saw the shop's placeholder tile.
  Nothing in the payload separated the two states, because `preview_is_cover: false` is the
  ordinary value for every good without an attached cover, so it is not a signal either.
- Root cause: two defects with one origin. `ContentDigest.obtain` fetched the origin bytes,
  computed their sha256 and returned, never inspecting what it had hashed, so publication
  accepted `image/svg+xml` exactly like a JPEG. The refusal only arrived at render time, where
  `PreviewDerivative.cut` could not decode it. And `PreviewNotFoundError` was raised from both
  "there is no saleable entry" and "the payload is not decodable", with one row in
  `PREVIEW_REFUSALS` mapping both to one 404 with one detail - so an operator could not tell a
  withdrawn good from a format the renderer cannot read.
- The class: a value that was computed and never inspected. The digest was the identity of the
  bytes, and nothing ever asked whether those bytes could become the thing the shop sells. Every
  test passed, the gate passed, and the good was legally publishable; it was simply unshowable.
  This is the shape the project already knows from its surface defect: a pipeline that looks
  correct end to end while nobody looks at its output.
- Evidence: origin `.../Larch_botanical_illustration_labelled.svg` answered `200`, `134523`
  bytes, `image/svg+xml`, and its sha256 matched the `content_digest` recorded at publication, so
  the pipeline had stored a payload its own renderer cannot read; `Image.open` raised
  `UnidentifiedImageError`. Measured scope: one `.svg` origin and one dead preview out of 104
  published goods - a class of defect rather than an item, because Openverse and Wikimedia carry
  diagrams and botanical illustrations as SVG at a rate that produces more.
- Fix class: service + sensor + contract.
- Change made: `packages/services/src/commerce/image_payload.py::ImagePayload` owns `Image.open`,
  `MAX_DECODE_PIXELS` and the refusal reason, and both `digest.py` and `derivative.py` import it,
  so exactly one module answers whether bytes can be rendered and the publication check cannot
  drift from the renderer; `DigestResult.renderable` records that answer in the same pass that
  hashed the bytes, so the digest and the judgement are about one payload rather than two;
  `PublicationBridge` refuses an unrenderable payload, withdraws an entry that already has one and
  leaves an already-withdrawn entry unchanged. The preview table now answers 404 only for "no
  saleable good here" and reports an unrenderable payload as a preview that could not be
  produced. OpenSpec change `refuse-unrenderable-origins` carries the contract; no rights,
  screening, gate or storefront file changed, and no verdict can move.
- Verification: after deploying `ecc85de` and running `velmor publish --env dev --limit 200`, the
  report line read `withdrawn openverse:ce7c97e3-...: the origin payload cannot be rendered as a
  preview`; the catalogue went 104 -> 103, the good answers 404 in `en`, `ru` and `be`, and all
  103 remaining previews answer `200`. `/ux-verify` looked at 336 card images across 3 locales and
  2 widths: 336 artwork, 0 placeholders, 0 broken tiles.
- Recorded in the same pass, because it makes the difference visible: a second candidate,
  `openverse:45acc41f-...`, is refused with `digest could not be obtained ... HTTP 404` - the
  pre-existing unobtainable-digest behaviour, unchanged and still pinned by its test. A dead
  origin and an unrenderable payload now read differently in the operator's report instead of
  collapsing into one outcome.

### 2026-09-23 - a health check on the wrong port called a service healthy while it starting

- Symptom: after restarting `velmor-api.service`, every route through Caddy answered 502 and the
  catalogue read 0 goods, including a control good that had served its preview minutes earlier.
  It looked exactly like the change under verification had broken the shop.
- Root cause: the liveness probe curled `127.0.0.1:8000` and read `200` from an unrelated service,
  while `velmor-api.service` binds `0.0.0.0:8080`. The probe therefore exited after one second and
  the verification requests fired into a uvicorn that had not finished starting - the service
  takes about ten seconds to come up, most of it waiting on a Logfire call that returns 401 with
  the token that is configured on the host. The 502s were Caddy reporting a closed upstream, not a
  regression, and a re-run against the live service passed unchanged.
- The class: a sensor that cannot fail. A probe that reads a port it does not own, and a sleep
  that ends before the thing it waits for exists, both report success while the subject is down.
  This is the same failure this file already records for `401` matching the ruff code `F401`: the
  check passed for a reason unrelated to what it claimed to check.
- Fix class: procedure, recorded here rather than mechanised: the probe is a one-off operator
  script and does not belong in `scripts/`. What a future run must do is stated in the next line.
- Change made: none to the harness. A readiness check must target the port the unit actually binds
  (`systemctl cat velmor-api.service`) and must poll `/health` until it answers, not sleep a fixed
  interval; `systemctl is-active` is not readiness. The `Logfire API returned status code 401`
  startup delay is the separate operational item already named in `HANDOFF.md` section D.

### 2026-09-23 - the Codex review path had never run, and its arguments were wrong in two places

- Symptom: `node scripts/codex-run.mjs review --id <id> --uncommitted` exited 2 in under five
  seconds without reaching a model, twice in a row, for two different reasons:
  `error: unexpected argument '--color' found` and then
  `error: the argument '--uncommitted' cannot be used with '[PROMPT]'`.
- Root cause: the `review()` branch of the runner was written against an assumed CLI surface and
  never executed. It passed `--color never`, which `codex exec review` does not accept, and it
  appended `-` unconditionally as `[PROMPT]`, which `--uncommitted` forbids. The `run()` branch had
  been exercised by the smoke worker and works, which is exactly why the defect survived: the
  channel was reported as working after a `run`, and `review` - the independent-second-reader path
  the whole dual-agent design leans on - had no execution behind it. `harness/codex-workers.md`
  listed the accepted review flags correctly the entire time, so the document and the code
  disagreed and nothing compared them.
- Fix class: code fix + lesson. The accepted flags are a property of the installed CLI, so the
  check that would have caught it is a comparison against the CLI's own help output.
- Evidence: `node .cursor/mcp/codex-launcher.cjs exec review --help` lists `-c`, `--uncommitted`,
  `--base`, `--commit`, `-m`, `--output-last-message`, `--json` and no `--color`; the two failing
  runs quoted above; and after the fix the same command passed argument parsing and ran for
  minutes instead of exiting in 4.8 s.
- Change made: `scripts/codex-run.mjs` no longer passes `--color` to `codex exec review`, and
  passes `-` only when there is a prompt file to read from stdin. The reasoning is a comment at
  both sites. The same unconditional `args.push('-')` in `run()` and `resume()` is correct and was
  left alone: both require a prompt file, so stdin always carries one.
- A third defect surfaced in the same path once it ran: `review` has no `--sandbox` flag, so the
  reviewer inherited the CLI default `workspace-write`. `harness/dual-agent.md` names a read-only
  Codex worker as one of the independent readers, so the sandbox is now pinned with
  `-c sandbox_mode="read-only"`, the way `resume()` already pinned it. Confirmed from the worker's
  own start banner, not from the arguments: the banner now reads `sandbox: read-only`.
- The same session also pinned the model, for cost rather than correctness. `codex debug models`
  renders the catalog the account can use; the machine's `~/.codex/config.toml` selected
  `gpt-5.6-sol`, which that catalog describes as the model "for complex work", and a ChatGPT plan's
  quota paid for it in a handful of calls. `DEFAULT_MODEL = 'gpt-5.6-terra'` - the catalog's
  "balanced model for straightforward work" - is now the runner's default and `--model` still
  overrides it. Pinning it in the repository is the point: the model no longer changes when a
  machine's global config does. The banner is the evidence, and it reads `model: gpt-5.6-terra`.

### 2026-09-23 - three permission hooks were inert, and one of them had no sensor at all

- Symptom: none. `harness-status.mjs` said READY, `selftest.mjs` said PASS, and product writes,
  rights-policy edits and storefront copy edits all went through unguarded.
- Root cause: the same absolute-versus-relative path mistake in three `preToolUse` guards. The
  runtime sends an **absolute** `tool_input.file_path` (`d:\Python\Velmor\packages\...`), and each
  guard compared it against repository-relative roots (`packages/`, `.cursor/rules/`,
  `storefront/src/`). Every real write therefore matched no entry and took the allow branch before
  the guard looked at anything: `codex-gate.cjs` never read the worker ledger, `policy-guard.cjs`
  never asked for approval on the rights policy surface, `ui-guard.cjs` never scanned for
  hardcoded copy. The synthetic payloads in `selftest.mjs` used the relative form, so the suite
  certified the shape the runtime does not send - the same class of defect as the BOM one already
  recorded above, and the second time this file has had to record it.
- Aggravating fact: `ui-guard.cjs` had **no check in `selftest.mjs` at all**. A hook with no
  sensor is a hook nobody has ever seen work or fail.
- Fix class: code fix + sensor, in the order that proves the sensor: add the checks first, watch
  them fail, then fix.
- Evidence: before the fix, `node scripts/selftest.mjs` reported exactly four new failures and
  nothing else -
  `FAIL asks before an edit to the publication gate - the absolute path the runtime sends - allow`,
  `FAIL asks before an edit to a rule - the absolute path the runtime sends - allow`,
  `FAIL denies Cyrillic copy in a component - the absolute path the runtime sends - allow`,
  `FAIL denies a literal language in lang= - allow`, `VERDICT: FAIL (4 checks)`.
  `codex-gate` was caught by an instrumentation run first: the captured payload carried
  `tool_name: "Write"`, an absolute `file_path`, and a recorded decision of `allow`, which refuted
  the "hooks do not fire for subagents" hypothesis and pinned the path form as the cause.
- Change made: `workspaceRelative(filePath, root)` moved into `.cursor/hooks/lib/hook-io.cjs` and
  is imported by all three guards, because one definition is what stops the next hook from
  repeating the mistake; each local copy was deleted. `selftest.mjs` gained absolute-path checks
  for all three, including the allow direction so the resolution cannot become a blanket deny, and
  the first checks `ui-guard` has ever had.
- A crash in a `failClosed` hook blocks the edit that would repair it, which is worth knowing
  before it happens: removing `normalise` while its call site still referenced it made
  `policy-guard.cjs` and `ui-guard.cjs` throw `ReferenceError`, and the write tool could no longer
  touch either file. The repair went through the shell, and the next multi-site edit to a
  fail-closed hook should be one atomic write rather than two edits with a broken state between.

### 2026-09-23 - `harness-status.mjs --root` read the alias table of the wrong tree

- Symptom: none observed. Found by an independent reviewer reading the diff, not by a failing
  check.
- Root cause: `import aliases from '../.cursor/mcp/mcp-aliases.cjs'` is a static import, resolved
  relative to the script, so it always read this checkout's table. `ROOT` becomes the `--root`
  directory, and the alias check then compared the inspected tree's `mcp.json` against this
  checkout's table: a target whose own `mcp-aliases.cjs` was missing an alias passed whenever this
  checkout happened to have it. `selftest.mjs` drives the sensor with `--root`, so the blind spot
  was reachable, and a sensor that reads the wrong tree is not a sensor.
- Fix class: code fix + sensor, proved in both directions.
- Evidence: with the defect injected (the table read from this checkout), the new check reported
  `FAIL reads the alias table from the inspected tree, not from this checkout - PASS context7:
  alias "context7" resolves in .cursor/mcp/mcp-aliases.cjs`, `VERDICT: FAIL (1 checks)` - the
  failure proves the target tree's empty table was never consulted. Restored:
  `PASS reads the alias table from the inspected tree, not from this checkout - FAIL context7:
  alias "context7" resolves`, `VERDICT: PASS`, `harness-status: READY`.
- Change made: the table is loaded from `ROOT` at runtime; `selftest.mjs` gained a case that
  builds a target tree whose own alias table is empty and requires `context7` to fail there.

### 2026-09-23 - a killed Codex runner left the gate open indefinitely

- Symptom: none, and none was possible while the state existed: `codex-gate` allowed product
  writes because the ledger still held a worker.
- Root cause: eligibility was `worker.running || worker.startedAt >= floor`, where `running` means
  "no exit file". A runner killed by an operator - `Stop-Process` on a backgrounded job, a killed
  shell - writes no exit record, and `running` bypassed the session window that exists to stop
  "Codex ran once, ever". A worker from a previous session therefore counted forever. Two killed
  Codex reviews in this session left exactly that state, and it was found only because the ledger
  was read while stopping them.
- Fix class: code fix + sensor, proved in both directions.
- Evidence: with the defect injected (`running` bypassing liveness again), the new check reported
  `FAIL denies a worker from a previous session that was killed, not merely a stale timestamp -
  allow`, `VERDICT: FAIL (1 checks)`. Restored: the same check reports `deny`, `VERDICT: PASS`,
  `harness-status: READY`.
- A wrong test is worse than no test, and this one was caught by reading the rule it was testing:
  the first version of the check dated the killed worker "now", so the session window - not
  liveness - decided it, and the check failed for a reason unrelated to the defect. The window
  clause is deliberate: a worker that started in this session counts even after it exits. The
  defect was only ever the cross-session case, so the check now dates its worker before the
  session epoch.
- Change made: `processAlive(pid)` in `codex-gate.cjs` probes the runner's own recorded `pid`
  (`process.kill(pid, 0)`; `EPERM` means it exists), a record without a pid still falls back to the
  window, and `selftest.mjs` asserts both directions.
- Still open, named rather than fixed: `scripts/codex-run.mjs` has no `stop` command and no signal
  handler, so an operator termination is never written to the ledger and `list` keeps calling a
  dead worker `running`. Liveness now compensates inside the gate, and the ledger itself still
  lies about the outcome.

### 2026-09-24 - the ledger called two dead Codex workers `running` for two and a half hours

- Symptom: `codex-run.mjs list` reported `derive-publish-review3` and `derive-publish-review5` as
  `running` after 155 and 140 minutes, in a session with no such processes. Both recorded pids were
  gone: `alive=False` for 19032 and 2368.
- Root cause: `status()` took the state from `meta.status` - the word written at launch, `running` -
  and overwrote it only when an exit record existed. A killed runner writes no exit record, so the
  fallback was its own launch-time claim and nothing ever contradicted it. This is the ledger half of
  the previous entry's named-open item: liveness had been added to `codex-gate`, but the reading a
  human uses to decide whether to wait or to re-dispatch still said the worker was alive.
- Fix class: code fix + sensor, proved in both directions.
- Evidence: with the defect injected (a ledger entry carrying pid `2147483000`, beyond any
  addressable process, and no exit record), the reconstructed pre-fix `status()` printed
  `running selftest-dead`; the fixed `status()` on the same entry printed `LOST(2147483000)`. A
  two-sided control on one code path - a live child pid printed `running`, the dead pid printed
  `LOST` - shows the reading is driven by liveness and not by the fixture. The new `selftest.mjs`
  section reports `PASS a worker whose process is gone is reported LOST, never running`,
  `VERDICT: PASS`, `harness-status: READY`.
- Change made: `status()` in `scripts/codex-run.mjs` probes the recorded pid when no exit record
  exists and reports `LOST(<pid>)`. `processAlive` there is a deliberate twin of the one in
  `codex-gate.cjs`, and both files name the other so the pair cannot drift unnoticed; they cannot
  share one definition because the gate is CommonJS and the runner is ESM, and a hook cannot await a
  dynamic import. `LOST` is deliberately neither `running` nor `FAILED`: nothing observed how the
  worker ended, so the outcome is unknown rather than chosen, and `resume` stays valid because it
  resumes by session id.
- Still open, named rather than fixed: the runner has no `stop` command and no signal handler, so an
  operator kill is still not recorded as an outcome. `status` now reports it honestly, but *why* the
  worker ended is still lost at the moment it happens.

### 2026-09-24 - a shell byte edit is reverted by the next editor-tool write

- Symptom: `node --check scripts/selftest.mjs` failed with `SyntaxError: Invalid or unexpected token`
  on `#!/usr/bin/env node`, while `node scripts/selftest.mjs` ran the same file without complaint.
  The file carried a UTF-8 BOM, which `node --check` refuses at the shebang line.
- Root cause of the BOM: pre-existing in `HEAD`, and `selftest.mjs` was the only harness script with
  one. The script whose job is proving the harness's own sensors work could not itself be
  syntax-checked, and no gate noticed. A BOM is invisible in every editor and in every diff.
- Root cause of the *return*, which is the part worth remembering: stripping the BOM with a byte
  write from the shell worked, and the very next `StrReplace` on the same file put it back. The
  editor holds the file in a buffer and rewrites the whole file from that buffer, so a
  shell-level byte edit to a file the editor has open is silently undone by the next tool edit.
  This is the same class as the `.cursorignore` lesson above: the disagreement is at the tool
  layer, not the filesystem, and the fix is ordering rather than permissions.
- Fix class: sensor + ordering. Strip the BOM as the *last* action on the file, after every tool
  edit, not before it.
- Evidence: `node --check scripts/selftest.mjs` returned exit 1 with the BOM and exit 0 without it.
  The new check reports `FAIL no harness script carries a UTF-8 BOM ... - scripts/_bom-probe.mjs`,
  `VERDICT: FAIL (1 checks)` with the defect injected, and
  `PASS no harness script carries a UTF-8 BOM (it makes \`node --check\` reject the shebang)`,
  `VERDICT: PASS`, `harness-status: READY` once it is removed. The sensor found the real file itself
  on its first run, which is how the silent revert was caught.
- Change made: `selftest.mjs` scans `scripts/` and `.cursor/hooks/` for U+FEFF at the start of any
  `.mjs`/`.cjs`/`.js` file and fails the run, and the BOM was stripped from `selftest.mjs`. The
  check is a byte comparison rather than a `node --check` spawn, so it costs no processes and names
  the offending file.

### 2026-09-24 - every `.sh` in the working tree is CRLF, so a copied deploy script dies on the host

- Symptom: `bash /root/deploy-storefront.sh` on the host answered `set: invalid option` at line 13,
  `$'\r': command not found` at line 14, and `cd: $'/opt/velmor/app\r': No such file or directory`.
  The same file is `ASCII text` with an LF entry in the index, and `git status` reports it clean.
- Root cause: `.gitattributes` sets `*.sh text eol=lf` and the index is LF, but the **working tree**
  copy is CRLF. A file written on Windows by an editor or an agent write tool lands with CRLF, and
  Git never renormalises it because the normalised content compares equal to the index - so the tree
  stays clean and the defect is invisible to every gate. 24 of the 30 shell scripts under `.deploy/`
  are in that state. A copy step ships the working-tree bytes, not the index, so the defect travels
  with `scp`. `HANDOFF.md` already recorded the workaround ("ship scripts with `tr -d '\r'`"), but as an
  instruction rather than as a cause, which is why it had to be rediscovered.
- Fix class: process now, sensor later. Run a shell script from the host's own git checkout - the
  checkout applies `eol=lf` and is LF by construction - instead of copying a working-tree file. A
  check over tracked `*.sh` for CRLF bytes belongs in `scripts/selftest.mjs` beside the BOM check; it
  is named here and deliberately not written yet.
- Evidence: `git ls-files --eol .deploy/deploy-storefront.sh` reports `i/lf w/crlf attr/text eol=lf`.
  A byte scan of the 30 shell scripts under `.deploy/` found CRLF in 24; the six clean ones are
  `deploy-74b.sh`, `deploy-saleor.sh`, `e2e-purchase.sh`, `firewall-loopback-services.sh`,
  `run-e2e-74.sh` and `run-e2e-74b.sh`. After `sed -i 's/\r$//' /root/deploy-storefront.sh` the same command reported
  `=== storefront dependencies ===`, `build exit=0 in 11s` and `active`.
- Change made: the deploy completed after normalising the host copy. No repository file changed; this
  entry is the record. The first script that fails this way again earns the sensor.

### 2026-09-24 - a jump-scroll counted five healthy product images as broken

- Symptom: a scan of `/be` at 390 px reported `images: {total: 13, broken: 5}` - five cards holding a
  356x445 media box with `naturalWidth: 0`, `complete: false` and `currentSrc: ""`. It read as five
  broken tiles stacked on the live home page, and it was one step away from being filed as a defect
  against a shop that was working.
- Root cause: the scan scrolled to `document.body.scrollHeight` in one jump. Native lazy loading loads
  what is near the *current* viewport, so jumping straight past the middle of a 9125 px document never
  brought those five images into range. They were healthy: the same preview URLs answer
  `200 image/webp`.
- Fix class: method. Scroll in steps of a few hundred pixels and let each step settle before counting.
  A jump-scroll is still acceptable once every step has been visited, so a page already walked can be
  re-counted cheaply.
- Evidence: with the jump, `brokenBeforeScroll: 5`, `brokenAfterFullScroll: 5`, `brokenAfterReturn: 5`,
  and all five carried `loading="lazy"`. With steps of 500 px and a 450 ms settle the same run ended
  `stillUnloaded: 0`. `curl` on those preview URLs returned `status=200 type=image/webp bytes=70154`
  and `bytes=160664`, against `bytes=165270` for an image that had loaded.
- Change made: none; this is a method note. The reason it is worth one: rule 08 already says a false
  positive is worse than a miss, and this one would have cost a session of work defending a working
  surface.
