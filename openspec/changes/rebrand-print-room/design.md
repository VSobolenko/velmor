# Design

## Layer and ownership

Everything here is `storefront/`, the one deliberate Node exception in the repository: a
presentation layer with no rights logic, no payment secret and no privileged credential. No
file under `packages/**` or `velmor/**` is touched, so the fixed dependency direction in
`.cursor/rules/02-architecture-layers.mdc` is unaffected by construction: there is nothing new
to place in a layer.

## Why Radix behind our own components

The repository rule is that a new dependency needs a stated reason. The reason is narrow and
testable: the behaviours we would otherwise hand-roll are the ones whose failure mode is an
accessibility defect, not a cosmetic one.

| Behaviour | What hand-rolling gets wrong | Radix primitive |
|---|---|---|
| Header menu, mobile nav | Focus is not trapped or restored; Escape does not close; roving tabindex | `react-navigation-menu`, `react-dialog` |
| Quick view, confirmations | No focus trap, no `aria-modal`, background stays tabbable | `react-dialog` |
| Tooltip on a licence term | No `aria-describedby`, shows on touch, cannot be dismissed | `react-tooltip` |
| Sort and filter selects | A styled `<select>` cannot carry swatches or a search field | `react-select` |
| Filter facets | No indeterminate state, no group semantics | `react-checkbox`, `react-radio-group` |
| Product facts and obligations | Accordion without `aria-expanded` and region wiring | `react-accordion` |
| Product/catalogue view switch | Tabs without arrow-key navigation | `react-tabs` |

The constraint that keeps this from becoming a rewrite: **a page never imports Radix.** Pages
import `@/components/ui/*`. The Radix import lives in exactly one file per behaviour, and that
file's exported API is ours. This keeps the surface we must maintain small and means a
primitive can be replaced without touching a page.

## The token set

`globals.css` defines the palette as CSS custom properties and exposes them to Tailwind through
`@theme inline`, so a utility class and a hand-written rule resolve to the same value and there
is exactly one place to change a colour.

Frozen values and their measured contrast ratios are in
`.superpowers/sdd/rebrand/identity.md`. Two of them are corrections, and they are the reason
this change exists rather than being cosmetic:

- `--color-muted` at `#6E6459` on paper measures **5.37:1**. The interim value (`slate-500` on
  `slate-50`) measured about **4.0:1**, below the 4.5:1 that AA requires of normal text. Every
  metadata line in the shop was failing.
- Form control borders need **3:1** under WCAG 1.4.11. The interim hairline was `1.28:1`. A
  second token, `--color-line-strong` at **3.49:1**, exists for control boundaries;
  `--color-line` stays for decorative dividers, where 1.28:1 is correct.

Keeping both tokens is deliberate: collapsing them would either make every divider heavy or
leave every control border non-conforming.

## Typography

`next/font/google` with `Playfair Display` for display and `Inter` for body, both with
`subsets: ["latin", "cyrillic", "cyrillic-ext"]`.

Both were verified to carry Cyrillic **before** being chosen, by requesting
`fonts.googleapis.com/css2?family=<name>` and reading the subset comments in the response. The
check is not ceremony: `Fraunces` returns `vietnamese, latin-ext, latin` and nothing else, so a
display choice that looked right in Latin would have silently fallen back for two of the three
locales. Any future font decision repeats that check.

Font loading is a build-time concern: `next/font/google` fetches at build. The existing build
already resolves two Google families on the deployment host, so this changes the family without
introducing a new requirement.

## The device, and how it is implemented

The hallmark is an SVG, not an image: it must stay crisp at 16 px in a badge and at 96 px in the
hero, and it must be recolourable from a token. Three forms, one geometry:

1. `Hallmark` - the mark alone, for badges, list markers and section rules.
2. `Wordmark` - `Proofbasket` in the display face with the two `o` glyphs replaced by hallmark
   medallions. Implemented as text plus two inline SVG medallions, not as an outline drawing, so
   it stays selectable, localisable and sharp.
3. `HallmarkPattern` - the weave tiled as a CSS `background-image` at 4 percent opacity, used
   behind the hero band only.

## Generated imagery: what it is for and what it may not be

Four images from Codex's `image_gen`, which is the only image generator wired up for this
repository and needs no `OPENAI_API_KEY`. Their role is bounded:

- `hero-printroom.png` - the hero band's imagery when the catalogue is empty, and the header
  band on account and checkout.
- `paper-texture.png` - a low-opacity fibre texture behind the hero band.
- `plate-placeholder.png` - the placeholder for a good whose preview is unavailable.
- `empty-basket.png` - the empty-state illustration.

The rule that governs them: **a generated image never stands in for the good.** A product card
shows the good's real preview or the plate placeholder, never a generated scene, and a product
page never presents generated art as the item for sale. This matters because the goods are
themselves images, and a buyer comparing two engravings must be looking at the actual engravings.

## Failure modes, and the one accepted

| Failure mode | Handling |
|---|---|
| A generated image introduces a colour outside the palette | Rejected and regenerated. The palette is checked, not assumed |
| `next/font/google` cannot reach the network at build | Build fails loudly at `next build`; it does not silently fall back. Accepted: a silent fallback would ship a different typeface per environment |
| A Radix primitive's styling leaks outside our wrapper | Contained by the one-file-per-behaviour rule; a page importing Radix is a review finding |
| The token change alters contrast in an untested pairing | Every pairing actually used is measured; a new pairing is a new measurement |
| The rebrand lands mid-rebuild and collides with page work | Sequenced: it runs after the page subagents land, against the frozen token file |

## Recorded deliberately not done

- **No rename and no domain change.** The brand keeps its name; only the visual language
  changes. A rename would touch the dictionaries, the disclosure, the API metadata and the
  deploy hostname, which is a separate decision with its own risk.
- **No custom font licensing.** Only Google-hosted, Cyrillic-capable families are used, so no
  font file is vendored and no licence obligation is added.
- **No motion system beyond what already exists.** A reduced-motion-respecting transition is
  kept; a scroll-driven animation layer is not built, because the shop's job is to be
  understood, and the research records carousels and autoplay as harmful.
