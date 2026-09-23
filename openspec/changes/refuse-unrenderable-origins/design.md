## Context

One published good has an origin payload the platform cannot render, so its advertised preview
resolves to `404` in every locale. Publication hashed those bytes and never looked at them; the
preview decodes them and refuses; the API maps the refusal to the status that means "there is no
good here". This design is about where the decision belongs, what it does to a good that is
already published, and how the refusal is reported without describing anything about the origin.

## Layer placement

| Piece | Layer | Why |
|---|---|---|
| `ImagePayload` | `packages/services/src/commerce/` | It decodes untrusted bytes with Pillow, and no `domain/` module may import an image library. It is shared by two sibling modules of the same layer, exactly as `AssetCache` is. |
| `DigestResult.renderable` | `packages/services/src/domain/digest.py` | A plain typed field with no behaviour and no import. The model stays a data container; the decision is made where the bytes are. |
| The identification | `packages/services/src/commerce/digest.py` | The port that already holds the bytes and already hashes them. |
| The refusal and the withdrawal | `packages/services/src/commerce/publication.py` | The bridge is the only place where a settled gate decision becomes a catalogue entry, so it is the only place that can refuse or withdraw one. |
| `PreviewNotRenderableError` | `packages/services/src/commerce/errors.py` | Where every commerce refusal already lives. |
| The status mapping | `packages/api/src/app.py` | The HTTP surface maps a typed refusal to a response. It decides nothing, so no policy is added there. |
| The buyer surface | `storefront/` | Unchanged. The media route already passes any status through and the component already shows the localised placeholder for a non-200. |

Nothing under `packages/services/src/rights/` or `packages/services/src/screening/` is touched,
the import direction is unchanged, and no agent, graph or model is involved anywhere in this
change:

Framework choice: plain Python, because every step is decidable from its inputs. Whether a
payload can be decoded is a property of the bytes; whether a good may be listed is already
decided by `PublicationGate`. There is no branching to model, no control flow to persist, no
extraction to perform, and no research to do, so LangGraph, Pydantic AI and DeepAgents are all
the wrong tool here for the reasons in `.cursor/rules/05-agent-graphs.mdc`.

## D1 - The identification rides on the digest port, and the decode lives in one imported class

The bytes exist in exactly one place: the response body that `ContentDigest.obtain` has already
fetched. Hashing and identifying are therefore the same pass over the same bytes, and the answer
belongs on `DigestResult`, which publication already receives.

That alone is not enough. If `ContentDigest` grew its own `Image.open` and its own idea of an
acceptable size, the platform would have two predicates for "can this be rendered", in two files,
that can drift. There is a live instance of that drift in the current code: the preview refuses a
payload whose declared pixels exceed `MAX_DECODE_PIXELS`, while publication would accept that
same payload and create an entry whose preview 404s. That is the defect this change exists to
remove, in a second form, so the new module exists to make it impossible:

`packages/services/src/commerce/image_payload.py::ImagePayload` owns

- the pixel bound (`MAX_DECODE_PIXELS`), moved here from `PreviewDerivative`;
- the refusal reason, as one constant, so the message the publication outcome carries cannot
  drift from the check that produced it;
- `frame(body) -> Image.Image`, which decodes the bytes, applies the bound, and raises
  `PreviewNotRenderableError` when it cannot;
- `can_render(body) -> bool`, the same operation with the answer as a value.

`PreviewDerivative` uses `frame` and keeps what is its own: the target format, the alpha decision
for WebP versus JPEG, the downscale, the encode and the cache. `ContentDigest` uses `can_render`.

Rejected: a differently named port. A port that fetches separately pays a second round trip and,
worse, can inspect different bytes than the ones it records a digest for, which would break the
identity between what was checked and what was published - the one property that lets an
operator trust the record. Rejected: renaming `ContentDigest` to something like `OriginPayload`.
Its product is still the digest, the identification is a by-product of the same pass, and a rename
would sweep the composition root, the `ContentDigestPort` protocol, `publication.py` and three
test modules for no behavioural change, with no transitional alias permitted in between.

## D2 - The refusal is a value on the publication path

`DigestResult` gains one field, `renderable: bool`. `obtain` returns it either way: the bytes were
obtained, hashed and cached exactly as before, and the field records what they are.
`PublicationBridge` reads it and returns a `PublicationOutcome` with
`action=REFUSED` and the reason taken from `ImagePayload`'s constant, mirroring
`_digest_for_publish`'s existing refusal for a missing `download_url`. No new catch is added on
the publication path, and the one existing catch there is unchanged.

One exception is translated inside `ImagePayload.can_render`: the typed refusal becomes the
boolean. The alternatives were evaluated. Letting `PreviewNotRenderableError` propagate would make
`velmor publish` abort partway through a pass instead of reporting a refusal for one good, which
is the opposite of what the publication contract requires. Returning `None` from the decode would
push the same branching onto every caller, and `None` in this codebase means a real absence rather
than an unasked question. The exception is ours, specific, carries the one reason, and the
translation is the logic that produces the value the contract asks for.

## D3 - An entry whose payload cannot be rendered is withdrawn; a fetch failure is not

The measured fact is that re-running the publication pass reaches an already published good
through the same `_when_paid_ok` path, and that the digest refusal currently returns before the
existing entry is consulted - so a published good whose payload cannot be rendered would be left
published, still advertising a preview that 404s. That is the outcome this change exists to
prevent, so the refusal is routed into the same shape the neighbouring causes already use:

| State of the entry | Outcome |
|---|---|
| No entry | `REFUSED`, with the reason, no entry created |
| Published | `WITHDRAWN`, with the reason recorded on the entry |
| Already withdrawn | `UNCHANGED`, with a reason saying the catalogue already matches |

The cause is a fact about the bytes, and the recorded digest is the identity of those bytes, so
the entry as it stands is one the shop cannot show. Withdrawal is the honest outcome now, and a
later pass whose origin payload can be rendered publishes the good normally.

An unobtainable digest keeps its existing behaviour: `REFUSED`, with an entry already published
left exactly as it was. That behaviour is documented and pinned by
`test_digest_unavailable_on_update_leaves_entry_unchanged`, and it is a statement about a fetch
rather than about the bytes: the good may still be deliverable from the cache, and the origin may
answer on the next pass. Extending withdrawal to fetch failures is a separate decision about
origin lifecycle, deliberately not taken here, and recorded below.

## D4 - The status split: 404 keeps one meaning, and the new case reuses the documented one

The requirement is that an operator can tell "this good is withdrawn" from "our renderer cannot
read this payload". Today both answer `404 'no preview exists for this good'`, so the non-decodable
case must leave `404`, and `PreviewNotFoundError` narrows to what it still means: unknown,
withdrawn, or not `PAID_OK`.

The replacement is the status the contract already fixes for "we could not produce a preview",
which names no origin and is already wired:

| Status | When |
|---|---|
| 404 | not in the catalogue, withdrawn, not `PAID_OK` |
| 409 | origin bytes no longer match the digest recorded at publication |
| 502 | the origin could not be reached, or it served a payload we cannot render |
| 500 | a cover is recorded for a good but its bytes are absent from the asset cache |

Why 502 for a payload we cannot decode, and not 404 or a new status:

- The origin answered `200` with bytes. Our own state is consistent and our cache is intact. What
  failed is turning an upstream payload into a preview, which is exactly what the existing "could
  not be produced" status means. Reporting it as "no such good" is the defect being fixed.
- `415` was considered and rejected. It describes the media type of a *request* payload, and a
  body-less `GET` cannot have an unsupported one; the code would be technically untrue and would
  teach an operator the wrong thing.
- A bespoke status where the contract already has one for this meaning adds a value to learn for
  no gain. Two 502 causes sharing one status is deliberate.

Why the buyer-visible detail string does not change, and no new one is added:

- The detail is the half a caller reads. It must stay fixed, origin-free, and silent about the
  payload: a body that says "not a decodable image" would describe the origin's bytes, and a body
  that names a format would let a caller fingerprint what the origin served.
- The operator's separating signal is the status. The cause itself is available where it belongs:
  the publication refusal reason, the recorded withdrawal reason, and the log - all operator-facing
  text that never reaches a response body.
- Reusing the existing string means one fewer message to keep honest, and no restating of a rule in
  prose (`.cursor/rules/08-evidence-and-sensors.mdc`).

The concealment guarantees are unchanged and are asserted where they already were: no response
body, header or refusal contains any part of the origin location, and the service-level test that
parameterises over the refusal types gains the new one.

## D5 - Why withdrawal rather than a cover or a render-time fallback

An operator can attach a cover to a good with no usable image, and a cover is served in place of a
preview. It was considered as the answer for this good and rejected:

- A cover is presentation substituted for a good's own bytes, and every good in this catalogue is
  itself an image. Publishing a good whose own image can never be shown means selling a picture the
  buyer cannot see, with a stand-in in its place. That is the failure the storefront rebuild
  removed, one layer down.
- It would make publication depend on an operator's later action: the same bytes would publish or
  not publish depending on whether somebody had attached a cover first. Publication decisions must
  be decidable from their inputs.
- Refusing is reversible without a human. Attaching a cover is a manual step on every such good,
  forever, and it leaves the underlying inability to render in place.

A render-time fallback was rejected for the same reason the defect exists: it would hide a state
the operator needs to see, and the buyer already has the placeholder.

## D6 - The cited contract table, and why the durable account is the spec

`packages/api/src/app.py::PREVIEW_REFUSALS` cites `.superpowers/sdd/redesign-storefront-ux/contract.md`
as the source of the table it implements. That file is gitignored (`.gitignore`, ".superpowers/"),
so it is local scratch state: a reviewer on a clean checkout cannot read the citation, and a rule
of the form "the code conforms to a file nobody has" is not a rule.

This change therefore does both, in one task:

- updates the preview table in that file, so the local working copy and the code agree, which is
  what the citation promises today;
- makes the durable account the OpenSpec spec, by citing
  `openspec/specs/commerce/storefront` from the `PREVIEW_REFUSALS` comment as well. The spec is the
  product contract, and it is now the thing the next reader can actually open.

## What the buyer sees, page by page

No page changes. The two surfaces that show a preview, and the pattern each follows:

| Surface | Locale keys it needs | States it renders | Image it shows | Pattern and source |
|---|---|---|---|---|
| Catalogue card (`ProductCard`) | none new; the existing `catalogue.*` keys | preview served, preview refused (placeholder), loading (skeleton), empty | the derived WebP from `/media/preview/{id}`, or `/brand/generated/plate-placeholder.webp` | A good whose bytes are absent shows a real placeholder, never a broken tile: `.cursor/rules/07-product-surface.mdc` section 3, and the "Anti-patterns" list in `.cursor/skills/storefront-ux/SKILL.md`, which records the broken-tile failure this surface was rebuilt from |
| Product page (`BuyBox`) | none new; the existing `product.*` keys, including the cover label | preview served, preview refused (placeholder), not found, cover shown and labelled | the same two assets | Buy box above the fold with a 4:5 media box: the same skill's layout table, rows "Product cards" and "Keep the buy box ... inside the first mobile viewport" |

Because the refused preview is replaced by the same asset in the same media box, the buyer's
reading of the page does not change with the status: a `404` and a `502` look identical to them,
which is the intended behaviour and is why the split is an operator affordance rather than a
buyer-facing one.

## Failure modes, and the one that is accepted

| Failure mode | Handling |
|---|---|
| The origin serves a payload the decoder cannot read | Refused at publication, or withdrawn if already published; asserted at the service, the bridge and the API |
| The payload decodes but is larger than the preview bound | Refused by the same predicate, so the oversized variant of this defect cannot be published either |
| The origin is unreachable during a pass | Refused; an existing entry is left as it was. Deliberately not withdrawn, and the asymmetry is recorded below |
| `Pillow` cannot decode a format it should | The refusal is over-wide: a good a future version could show is refused today. Accepted, because the alternative is publishing a preview that may not exist, and the cause is recorded so the decision is auditable |
| A re-publication pass is never run after this lands | The already-published good keeps its dead preview until it is. Handled by an explicit task with its own evidence rather than assumed |

Accepted deliberately: one extra decode per publish pass per good. The check has to be about the
same bytes in the same pass, the bytes are already in memory, and a publication pass runs per
operator invocation rather than per request, so the cost is bounded and the alternative - a second
fetch, or a predicate that can disagree with the renderer - is worse.

## New dependencies

None. `pillow>=12.1.0` is already a direct dependency of the workspace (`pyproject.toml`) and is
already the only parser of untrusted bytes the platform runs; this change moves where it is called
from, not what is called. No security note is added because no new surface is added: the decode
runs on our server over bytes we already fetch and hash, over the same bound
(`MAX_DECODE_PIXELS`) that the preview path already applied.

## Deliberately not done

- **Rendering SVG.** No renderer, no conversion service, no new dependency. Rasterising a diagram
  would also change what the buyer is buying, which is a product decision, not a repair.
- **Extracting an embedded raster from an SVG.** A second decoder with its own failure modes, for a
  payload we have decided not to sell.
- **Withdrawing on an unobtainable digest.** Recorded in D3. What would have to be true: a decision
  that a good whose origin has gone is no longer deliverable from the cache either, which is a
  statement about origin lifecycle rather than about image formats.
- **A cover rescuing an unrenderable good.** Recorded in D5.
- **Publishing a non-image good.** Every card advertises `preview_url`, so the uniform rule is that
  publication requires a renderable payload. What would have to be true to publish a text or audio
  good: the read model must stop advertising a preview for a good that has none, and the card and
  product page need a designed state for a good with no image at all - which is a storefront change
  with its own specification.
- **Folding the payload condition into the existing entry-existence requirement.** See the proposal.
  What would have to be true: `redesign-storefront-ux` and `rebrand-print-room` merged into
  `openspec/specs/`, so that no two changes are editing one requirement at once.
- **Enforcing "no image library inside the deterministic surface" mechanically.** The layering test
  checks the agent stack, not Pillow, so a `domain/` module could import it today and the suite
  would stay green. This change keeps Pillow out of `domain/` by construction and does not enlarge
  a sensor about previews; adding the rule is a change about the architecture sensor.

## Risks

- **The refusal is over-wide rather than wrong.** A payload the decoder rejects is refused even if
  it is arguably sellable. Bounded by the fact that the payload must be decodable for the shop to
  show it at all, and recorded with its cause so the decision can be reviewed.
- **The repair is an operational step.** A code change cannot withdraw a stored entry by itself;
  the pass has to run. Mitigated by a task that runs it and quotes the report, in dev and on the
  deployed shop, and by the buyer-surface verification that looks at the result.
