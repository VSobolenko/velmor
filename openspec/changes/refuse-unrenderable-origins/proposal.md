## Why

`velmor publish` published a good whose preview can never be produced. The buyer sees the
placeholder instead of the artwork, and nothing in the platform says so.

The chain, verified end to end:

- candidate `openverse:ce7c97e3-e1dc-4576-874c-c981cb49d04e`, "Labelled Botanical Illustration
  of a Larch";
- origin `https://upload.wikimedia.org/wikipedia/commons/7/77/Larch_botanical_illustration_labelled.svg`,
  answering `200`, `134523` bytes, `image/svg+xml`;
- sha256 of the fetched body `4f45ddb8bdc3858c2c417be18b0f81c7160e92b6e6e04dd9b5cc0a8facc7015a`,
  recorded as `content_digest` at publication;
- `Image.open` raises `UnidentifiedImageError`, so the preview route answers
  `404 'no preview exists for this good'` in every locale.

`ContentDigest.obtain` fetches the origin, hashes it and returns the digest, and never inspects
what it hashed, so an SVG passes publication exactly like a JPEG. The refusal arrives later, at
render time, as `PreviewNotFoundError`, which the API reports with the same status and the same
detail as "this good is not in the catalogue". Nothing in the payload separates the two:
`preview_is_cover` is `false` for every good without an attached cover, which is the ordinary
state and therefore not a signal.

Measured scope: 104 published entries, exactly one `.svg` origin, exactly one dead preview. It
is a class of defect rather than one item, because Openverse and Wikimedia carry diagrams and
botanical illustrations as SVG at a rate that will produce more.

The cost of the current shape is not one 404. It is that a correct publication decision can
produce a good the shop advertises and can never show, and that an operator's only signal is one
status code that means four different things.

### The licence concern, stated explicitly

- **Which licence action.** Unchanged: selling a download is `RightsAction.RESELL`, decided by
  the existing `PublicationGate`.
- **Which evidence.** Unchanged. This change reads no rights input, no `RightsRecord` and no
  `Evidence`. It inspects the bytes at the `download_url` the candidate already carries.
- **What the platform refuses when the evidence is missing.** A good whose origin payload the
  platform cannot render is refused at publication, or withdrawn if it is already published,
  with a reason. The catalogue therefore contains only goods whose image the shop can actually
  produce.

### Effect on existing verdicts

None. The rights engine, the policy table, `PublicationGate` and `RightsResolver` are not
touched, no evidence kind is added and no gate condition changes. `ENGINE_VERSION` does not
move, and a verdict computed from the same inputs before and after this change is identical.
What changes is what happens after a verdict: a publishable good whose payload cannot be
rendered no longer becomes a catalogue entry.

### What the buyer will see

The buyer's experience does not change, and that is the point of the change rather than a
shortcoming of it:

| Surface | What the buyer sees |
|---|---|
| Catalogue card and product page | A preview image for a good whose bytes can be rendered, exactly as today |
| Catalogue card and product page, preview refused | The shop's own plate placeholder, as today: never a broken tile, never an empty box, never a line of text |
| The catalogue as a whole | One fewer good: the good whose image can never be shown is no longer on sale, so no card advertises a preview that does not resolve |
| Every locale | Unchanged. No page, no component, no layout and no copy changes |

Localisation: this change adds no buyer-visible string, so the dictionaries under
`storefront/src/lib/i18n/` are not touched and no locale is added or removed. The only
buyer-visible change is which status code a refused preview carries, and a browser does not
render a status code: `PreviewImage` already replaces any failing image with the localised
placeholder asset and the good's own title. No English-only or single-language surface is
introduced, because no surface text is introduced at all.

## What Changes

- **Publication learns what it hashed, in the same pass.** The port that fetches the origin
  bytes is the only place that has them, so the digest result carries whether a preview can be
  produced from them, and publication refuses the good when it cannot. The refusal is a value
  on the publication path, in the shape of the existing refusal for an unobtainable digest, and
  its reason names the cause and names no origin.
- **A published good whose payload cannot be rendered is repaired, not left.** The next
  publication pass withdraws it, with the withdrawal reason recorded, so nothing stays on sale
  while its preview 404s forever. Decided: withdrawal, not rasterisation, not an embedded
  raster, not a substitute cover, and not a render-time fallback that hides the state.
- **The preview refusals become distinguishable.** `404` keeps its single meaning, "there is no
  saleable good here": unknown, withdrawn, or not `PAID_OK`. A payload the platform cannot
  render is reported as a preview that could not be produced, which is the contract's existing
  status for that meaning. An operator can now tell a withdrawn good from a format the renderer
  cannot read; a buyer learns nothing new, and no response names or describes the origin.
- **One place answers whether bytes can be rendered.** The decode, the pixel bound and the
  refusal reason are used by both the publication check and the preview cut, so the two cannot
  disagree about what "renderable" means. This is what makes the oversized-payload variant of
  the same defect impossible rather than merely unfixed.

## Capabilities

### New Capabilities

None. Both behaviours extend capabilities that already exist.

### Modified Capabilities

- `commerce/catalog-publication`: a good is listed only while the platform can produce a
  preview from its origin payload; a payload that cannot be rendered is refused with a reason,
  and an entry already published for such a good is withdrawn by the next pass.
- `commerce/storefront`: the preview endpoint's refusals are distinguishable - `404` means no
  saleable good, a preview that could not be produced is reported as such, and the buyer sees
  the shop's placeholder either way.

Both are written as ADDED requirements rather than as modifications of requirements that
already exist. For `commerce/storefront` the preview contract lives only in the unmerged
`redesign-storefront-ux` delta, and for `commerce/catalog-publication` the two in-flight
changes must be free to merge `openspec/specs/` first; two changes editing one requirement in
parallel is how a contract gets corrupted. Folding the payload condition into
"An entry exists only while its decision is publishable and saleable" is a follow-up edit once
those merges have landed, and it is named in `design.md`.

## Non-goals

- **No rasterisation and no SVG support.** No renderer is added, no embedded raster is
  extracted, and no rasterisation dependency is introduced. The human declined this, and
  refusing is cheaper and more honest than guessing what a diagram means.
- **No new dependency of any kind.** Pillow is already a direct dependency
  (`pyproject.toml`, `pillow>=12.1.0`) and is used exactly where it is already used.
- **No change to the rights path.** No verdict can move, no policy file is edited, and
  `ENGINE_VERSION` does not move.
- **No change to what a buyer sees.** No page, no component, no string, no layout and no
  locale. A refused preview shows the placeholder that already exists.
- **No cover-based rescue.** An operator-attached cover does not make an unrenderable good
  publishable. Reasoning in `design.md`.
- **No change to delivery.** A good already sold keeps delivering the bytes it was sold with.
- **No change to how a digest is obtained for a good we publish.** The same fetch, the same
  hash, the same cache decision.
- **Not fixing the digest-unavailable case.** A fetch failure on a re-publication still leaves
  an existing entry as it was. It is a different statement about a different thing, and it is
  pinned by an existing test.
- **No new architecture sensor.** The layering test does not forbid Pillow inside the
  deterministic surface; this change keeps it out by construction and does not enlarge a
  sensor about previews.

## Impact

**Code**

- `packages/services/src/commerce/image_payload.py` - new: the one place that decides whether
  bytes can become a preview.
- `packages/services/src/commerce/derivative.py` - delegates its decode and its pixel bound.
- `packages/services/src/commerce/digest.py` - records the identification of the bytes it
  hashed.
- `packages/services/src/commerce/publication.py` - refuses an unrenderable payload and
  withdraws an entry whose payload is no longer renderable.
- `packages/services/src/commerce/errors.py` - one new refusal; the docstring of
  `PreviewNotFoundError` narrows to the cases it still means.
- `packages/services/src/domain/digest.py` - one plain typed field.
- `packages/api/src/app.py` - one row in `PREVIEW_REFUSALS` and a durable citation.
- `.superpowers/sdd/redesign-storefront-ux/contract.md` - the preview table the API cites. The
  file is gitignored local state, which is why the same task also makes the citation durable.

**Tests**

`packages/services/tests/unit/commerce/test_image_payload.py` (new), `test_digest.py`,
`test_publication.py`, `test_preview.py`, `test_covers.py`,
`packages/api/tests/unit/test_catalogue_preview.py`, and a new
`velmor/tests/unit/test_publish_command.py` for the report the operator reads.

**Storage and systems**

No schema change: `DigestResult` is in memory and `CatalogueEntry` is unchanged, so
`ensure_schema()`'s create-never-alter limitation is irrelevant here. Saleor is untouched. No
new setting, and no setting becomes optional.

**Risk**

The main risk is a refusal that is too wide: a good whose image a future version could handle
is refused today. Mitigated by refusing only what the platform's own decoder refuses, by
recording the cause so the decision is auditable, and by publishing normally again as soon as
an origin payload can be rendered. The second risk is that the live catalogue keeps the dead
good until the repair pass runs, which is handled by an explicit task rather than left to the
next deploy.
