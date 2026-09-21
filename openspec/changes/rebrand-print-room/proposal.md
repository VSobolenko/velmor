## Why

`redesign-storefront-ux` gives the shop a correct structure: cards, previews, localisation,
search. It does not give it an identity. Measured on the live deployment, what a buyer sees is
a generic Tailwind surface: system-default buttons, a bare header, three stock PNGs in
`storefront/public/brand/`, and no mark of any kind. Structure without identity is a template.

The human rejected the previous iteration in exactly these terms, and asked for a shop that is
recognisable at a distance and carries a real brand rather than primitives. This change
replaces the placeholder visual layer with a designed one.

### The licence concern, stated explicitly

- **Which action.** Unchanged: selling a download is `RightsAction.RESELL`, decided by the
  existing `PublicationGate`.
- **Which evidence.** Unchanged. This change reads no rights data at all. It is presentation.
- **What the platform refuses when evidence is missing.** Unchanged. Nothing here can add a
  catalogue entry, publish a good, or reach the gate.

### Effect on existing verdicts

None. `ENGINE_VERSION` does not move. No evidence kind, alias or gate condition is touched.

### The buyer-surface section (required by the project rules)

What the buyer will SEE, page by page:

| Surface | What changes for the buyer |
|---|---|
| Every page | A warm paper surface instead of white; a display serif for headings; the hallmark device in the header, on licence badges and as section rules |
| Home | A print-room hero band with the wordmark, a trust strip, category tiles with real imagery, a featured grid |
| Catalogue | Product cards carrying a preview image, a title, the licence and a price, on a paper surface |
| Product | The buy box above the fold: 4:5 preview, title, price, one filled full-width primary action, one licence cue; the sticky action bar appears only after the buy box leaves the viewport; obligations and facts in accordions below |
| Cart and checkout | The same components, a cart drawer that opens on add, provider selection as labelled cards, the seller disclosure presented before payment |
| Account | Orders and entitlements as cards with state badges, a download action per valid entitlement |
| Empty, loading, error, not-found | Illustration plus a single clear action, in every locale |

Localisation ships in this change: every new string is added to `ru`, `be` and `en` in the
same task that uses it, and no language is chosen for the buyer. No English-only surface is
introduced.

## What Changes

- **A visual identity, frozen as tokens.** Warm paper, deep ink, a vermilion seal accent and a
  display serif, specified in `.superpowers/sdd/rebrand/identity.md` with every contrast ratio
  computed rather than estimated.
- **The hallmark.** One device, derived from the name, used to mark verified things, and a
  wordmark whose two `o` glyphs are the device. This is what carries recognition.
- **Generated imagery, used only where there is nothing real to show.** Four images from
  Codex's `image_gen`, in the palette, never presented as the good itself.
- **A real component layer.** Radix primitives behind our own components for the behaviours
  that are unsafe to hand-roll: menu, dialog, tooltip, select, checkbox, radio group, tabs,
  accordion. Our components keep the caller-facing API; Radix is never imported by a page.
- **A correction to two measurable defects.** Secondary text moves from about 4.0:1 to 5.37:1
  and form control borders from 1.28:1 to 3.49:1, both verified.
- **Retirement of the interim layers.** The `--pb-*` CSS bridge, `shop.module.css` and
  `lib/copy.ts` are deleted once nothing imports them, and the `LEGACY_IMPORTERS` allowlist in
  `check-i18n.mjs` is emptied so the guard stays honest.

## Capabilities

### Added Capabilities

- `commerce/brand-identity`: what the shop's visual identity IS, as requirements a reviewer can
  check - the token set, the contrast floor, the target-size floor, the device, the imagery
  rules, and the requirement that typography covers every supported locale.

### Modified Capabilities

None. `redesign-storefront-ux` already modifies `commerce/storefront`, and two changes editing
one requirement in parallel is how a contract gets corrupted. The rebrand's own constraints
live in the new capability, and `commerce/storefront` continues to describe behaviour.

## Non-goals

- **No rename.** The brand stays `Proofbasket`; the wordmark changes, the name does not.
- **No change to the rights engine, the API contract or the database.** This is source under
  `storefront/` plus generated assets.
- **No new payment, provider or credential behaviour.**
- **No second decorative motif.** One device, consistently applied, is the point.
- **No replacement for real catalogue imagery.** Generated art fills gaps only.

## Impact

**Code**

- `storefront/src/app/globals.css` - the token set replaces the interim one.
- `storefront/src/app/layout.tsx` - the font pairing.
- `storefront/src/components/ui/**` - rebuilt on Radix where a behaviour is involved.
- `storefront/src/components/**` - header, footer, cards, states, cart drawer.
- `storefront/src/app/[locale]/**` - every page re-skinned against the tokens.
- `storefront/src/lib/copy.ts`, `storefront/src/app/shop.module.css` - deleted.
- `storefront/scripts/check-i18n.mjs` - the allowlist emptied.
- `storefront/public/brand/**` - the stock PNGs replaced by generated counterparts.

**Dependencies**

- New under `storefront/` only: `@radix-ui/react-*` for menu, dialog, tooltip, select,
  checkbox, radio-group, tabs and accordion. Approved explicitly by the human for this change.
  Reason: focus management, escape handling, roving tabindex and ARIA wiring are the parts of a
  design system that are genuinely unsafe to hand-roll, and a wrong implementation is an
  accessibility defect rather than a style choice. No Python dependency changes. Security note:
  the packages are unprivileged, browser-side, and hold no secret; they do not enter the API
  image or the Python environment.

**Risk**

- A visual overhaul is wide and touches every page. Mitigated by doing it after the page
  subagents land, against a frozen token set, with the runtime verification last rather than
  interleaved.
- Generated imagery can drift outside the palette. Mitigated by rejecting any asset that
  introduces a colour outside the table in the identity spec.
