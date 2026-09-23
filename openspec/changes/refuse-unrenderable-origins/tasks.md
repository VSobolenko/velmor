# Tasks

Ordered so the shared decision is complete and tested before anything depends on it. Each task is
a unit one implementer can finish and a reviewer can judge on its own. Tests are in the task that
adds the behaviour.

## 1. One place answers whether these bytes can be rendered

- [ ] 1.1 Add `packages/services/src/commerce/image_payload.py` with `ImagePayload`, holding the
      decode, the pixel bound (`MAX_DECODE_PIXELS`, moved out of `PreviewDerivative`), the refusal
      reason as one constant, `frame(body) -> Image.Image` and `can_render(body) -> bool`, and add
      `PreviewNotRenderableError` to `packages/services/src/commerce/errors.py` with a docstring
      that says the payload is not one the platform can render and that the message must not name
      the origin. Verify: a new `packages/services/tests/unit/commerce/test_image_payload.py`
      asserts a PNG payload is renderable and its frame decodes to the payload's dimensions; an
      SVG payload (`b'<svg xmlns="http://www.w3.org/2000/svg"/>'`) is not renderable, `frame`
      refuses it with the typed error, and `can_render` answers `False` rather than raising; a
      payload whose declared pixels exceed the bound is refused by both methods; a truncated PNG
      is refused by both. Then prove the check can fail: revert `frame` to return a frame without
      the bound and without translating Pillow's raises, show the new assertions failing, and
      restore. Quote both runs.

- [ ] 1.2 Point `PreviewDerivative` at `ImagePayload.frame` and delete its own `Image.open`, its own
      bound and its own translation of Pillow's errors, so `derivative.py` contains no
      `Image.open`, no `MAX_DECODE_PIXELS` and no `except OSError`. Update the three service-level
      tests that pin the old refusal type for a non-image payload:
      `test_preview.py::TestPreviewRefusals::test_a_payload_that_is_not_an_image_is_refused`,
      `test_covers.py`'s refusal case for a non-image cover file, and the parameterised
      `test_no_refusal_message_names_the_origin` list, which gains the new type. Verify:
      `uv run python -m pytest packages/services/tests/unit/commerce -q` passes; the cover path
      still refuses a non-image file, now with `PreviewNotRenderableError`; and a reviewer can see
      that `MAX_DECODE_PIXELS` and the refusal reason each appear in exactly one module
      (`rg "MAX_DECODE_PIXELS|NOT_RENDERABLE_REASON" packages`).

## 2. Publication refuses, and repairs

- [ ] 2.1 Add `renderable: bool` to `DigestResult` and set it in `ContentDigest.obtain` from
      `ImagePayload.can_render(body)` over the same body it hashes, leaving the fetch, the hash,
      the size and the cache decision exactly as they are. Verify: `test_digest.py` gains a case
      asserting a PNG body yields `renderable is True`, and a case asserting an SVG body yields
      the correct digest and size, `renderable is False`, and the body still cached when it fits
      the budget; the existing success, HTTP-error, transport-failure, over-threshold and
      blank-URL cases are unchanged and pass.

- [ ] 2.2 Refuse an unrenderable payload in `PublicationBridge` and withdraw an entry that no
      longer has one, in the shape the neighbouring causes already use: no entry -> `REFUSED` with
      the reason; published entry -> `WITHDRAWN` with the reason recorded; already withdrawn entry
      -> `UNCHANGED` with a reason saying the catalogue already matches. Build the refusal reason
      from `ImagePayload`'s constant rather than writing it again in the bridge, and do not change
      what an unobtainable digest does. Verify: `test_publication.py` gains the three cases, each
      asserting the action, the entry state, that `reasons` is non-empty, that the reason contains
      the constant, and that the reason contains no origin URL; a fourth case asserts the two
      refusal causes are distinguishable in one run (an unrenderable payload withdraws, an
      unobtainable digest leaves the entry published); and
      `test_digest_unavailable_on_update_leaves_entry_unchanged` still passes unmodified.

- [ ] 2.3 Make the cause visible in the operator's report. Verify: a new
      `velmor/tests/unit/test_publish_command.py` builds the command over a complete fictional
      `.env` (the fixture `packages/api/tests/unit/configs/test_settings.py` already provides),
      calls the report method the publish loop uses for a `WITHDRAWN` outcome carrying the reason,
      and asserts through `capsys` that the candidate id, the action and the reason are printed and
      that no origin URL is in the output.

## 3. The refusal contract

- [ ] 3.1 Map the new refusal at the HTTP surface. Add
      `PreviewNotRenderableError: (502, 'the preview could not be produced')` to
      `PREVIEW_REFUSALS`, narrow `PreviewNotFoundError`'s docstring to the cases it still means
      (unknown, withdrawn, not `PAID_OK`) and correct the comment above the table, which currently
      counts four documented errors. Verify: `packages/api/tests/unit/test_catalogue_preview.py`'s
      `test_a_payload_that_is_not_an_image_is_404` becomes a 502 assertion and is renamed; the
      withdrawn-good and unknown-good cases stay 404; a new case asserts the two are distinguishable
      by status; a new case asserts the 404 and 502 bodies are the fixed details and contain no
      origin; and `uv run python -m pytest packages/api -q` passes.

- [ ] 3.2 Update the cited contract table in
      `.superpowers/sdd/redesign-storefront-ux/contract.md` so its preview rows match the code
      (`404` for not in the catalogue, withdrawn or not `PAID_OK`; `502` for an unreachable origin
      or a payload that cannot be rendered), and make the citation durable by having the
      `PREVIEW_REFUSALS` comment name `openspec/specs/commerce/storefront` as well. Note for the
      implementer: that file is gitignored local state, so a reviewer on a clean checkout cannot
      read it; the durable half of this task is the comment and the spec. Verify: the two rows and
      the comment are quoted in the task report, and a reviewer can see that no other row changed.

## 4. The repair, and the buyer surface by looking at it

- [ ] 4.1 Repair the already-published good. Run
      `uv run velmor publish --env dev --limit 200` and quote the report line for
      `openverse:ce7c97e3-e1dc-4576-874c-c981cb49d04e`: it must read `withdrawn` with the refusal
      reason, and the summary must count exactly one more withdrawal than before. Then confirm the
      catalogue no longer lists it and that
      `GET /catalogue/goods/openverse:ce7c97e3-e1dc-4576-874c-c981cb49d04e` and its preview both
      answer not found, in `en`, `ru` and `be`. Then deploy and repeat the same three checks on the
      deployed shop. Verify: quote the report line, the summary counts, the three API responses and
      the same three responses from the deployed host. A repair that is only asserted in dev is not
      the repair the defect needs.

- [ ] 4.2 Verify the buyer surface by looking at it. Run `/ux-verify` against the running shop and
      record screenshots of the catalogue and of one product page at 390 px and 1440 px in `en`,
      `ru` and `be`, showing previews rendered as images, no broken tile anywhere, and, for a good
      whose preview is refused, the shop's own placeholder. To have a refused preview on a listed
      good, produce the state on the dev stack only, with no product-code change: point one dev
      entry's `origin_url` at a payload the platform cannot render (the Wikimedia SVG from the
      evidence is a payload that fetches successfully) and set its `content_digest` to the sha256 of
      that payload's bytes, look at it, then revert the row - or re-run the publication pass after
      restoring the origin. If that origin is unreachable from the verifying host, the 500
      cover-bytes-missing refusal is an acceptable substitute for the screenshot only, and the
      report must name which refusal was induced. Verify: the screenshots are the evidence, the
      induced cause is named, the dev row is reverted, and a passing suite is explicitly not
      offered in place of the screenshots.

- [ ] 4.3 Record the defect in `harness/lessons.md` (append only, with symptom, root cause, fix
      class, evidence and change made), naming the class: a value that was computed and never
      inspected, so a legal decision produced an unshowable good and no gate could see it. This
      task is Cursor's work and must not be delegated to a Codex worker, since `harness/**` is the
      harness itself; expect `policy-guard.cjs` to ask for human approval. Verify: the entry is
      appended, no earlier entry is edited, and `node scripts/harness-status.mjs` still reports
      `harness/lessons.md` present.

## 5. Gates

- [ ] 5.1 Run the change's own contract check and the standing gates, quoting output rather than
      summarising it: `uv run ruff check`, `uv run python -m pytest packages -q`,
      `uv run python -m compileall -q packages velmor`,
      `openspec validate --strict "refuse-unrenderable-origins"`. State explicitly whether
      `node scripts/selftest.mjs` was run: it is required only if a file under `scripts/` changed,
      and this change does not touch one. Verify: the four command outputs are quoted, and any
      command not run is reported as unverified rather than implied to have passed.

- [ ] 5.2 Run `/rights-verify` and state the outcome of the verdict path explicitly, including
      that `RightsResolver.ENGINE_VERSION` did not move and that the publication gate still refuses
      what it must. Verify: the command's output is quoted, and the report says plainly that
      publication changed and the verdict path did not.
