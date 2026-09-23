# Tasks

Ordered so that the frozen layer lands first and every later task builds against it. Each task
is a unit one implementer can finish and a reviewer can judge on its own.

## 1. Tokens, typefaces and the Tailwind theme

- [ ] 1.1 Replace the colour custom properties in `storefront/src/app/globals.css` with the frozen
      token set from `.superpowers/sdd/rebrand/identity.md`, exposed to Tailwind through
      `@theme inline`. Keep `--color-line` for decorative dividers and add
      `--color-line-strong` for control boundaries.
- [ ] 1.2 Switch the font pair in `storefront/src/app/layout.tsx` to Playfair Display (display)
      and Inter (body), exposed as `--font-display` and `--font-body`. Inter takes the `latin`,
      `cyrillic` and `cyrillic-ext` subsets. Playfair Display does not offer `cyrillic-ext` and
      requesting it fails the build, so it takes `latin` and `cyrillic` only; its `cyrillic` subset
      covers the Belarusian characters.
- [ ] 1.3 Add the display scale, the radius scale and the spacing rhythm as theme values, so a
      page composes from named steps instead of ad-hoc utilities.
- [ ] 1.4 Record the computed contrast ratio of every pairing the token set is used in, in the
      task report. A pairing that is used but not measured is an unfinished task.

## 2. The hallmark device

- [ ] 2.1 Implement `storefront/src/components/brand/Hallmark.tsx`: the mark as inline SVG on a
      `0 0 24 24` viewBox, geometrically as specified in the identity file, recoloured from a
      token, with a size prop and a `title` for assistive technology where it carries meaning.
- [ ] 2.2 Implement `storefront/src/components/brand/Wordmark.tsx`: `Proofbasket` in the display
      face with the two `o` glyphs replaced by hallmark medallions, as text plus inline SVG
      rather than an outline drawing, so it stays selectable and localisable. The accessible
      name SHALL be the brand name as a plain string.
- [ ] 2.3 Implement `storefront/src/components/brand/HallmarkRule.tsx` and the 4 percent weave
      background used behind the hero band. The weave SHALL NOT be placed behind body text at a
      higher opacity.
- [ ] 2.4 Implement `storefront/src/components/brand/HallmarkBadge.tsx` for the licence and
      verification cue, using the `accent-soft` and `accent-strong` tokens.

## 3. Radix primitives behind our own components

Each row is one file under `storefront/src/components/ui/`, exporting our API. A page importing
Radix directly is a review finding.

- [ ] 3.1 `Menu` on `@radix-ui/react-navigation-menu`; rebuild the header navigation and the
      mobile drawer on it, with focus restoration and Escape handling.
- [ ] 3.2 `Dialog` on `@radix-ui/react-dialog`; rebuild `Sheet` and the cart drawer on it, with
      a focus trap and `aria-modal`.
- [ ] 3.3 `Tooltip` on `@radix-ui/react-tooltip` for a licence term's explanation, dismissible
      and not shown on touch.
- [ ] 3.4 `Combobox` and `Listbox` on `@radix-ui/react-select` for sort and locale selection,
      replacing the native `<select>` where the option needs more than a string.
- [ ] 3.5 `Checkbox` and `RadioGroup` on their Radix primitives for the catalogue facets and the
      payment provider choice, with an indeterminate state where a facet has partial selection.
- [ ] 3.6 `Tabs` and `Accordion` on their Radix primitives for the product page's facts,
      obligations and related goods, with arrow-key navigation and correct region wiring.
- [ ] 3.7 Add the dependencies to `storefront/package.json` only, and confirm the server build
      and the API image are unaffected.

## 4. The component layer

- [ ] 4.1 `Button`: variants for primary, secondary, ghost, danger and a link-styled action;
      sizes; a pending state that is not a spinner glued on top; correct disabled semantics.
      Primary is the filled seal button; a page has at most one per view.
- [ ] 4.2 `Card`, `Badge`, `PriceTag`, `Input`, `Textarea` with an error state, and `Select`, all
      rebuilt against the tokens and audited for label wiring. The error state is a prop on the
      control, wired to `aria-invalid`, `aria-describedby` and a `role="alert"` message; it is not a
      separate wrapper component.
- [ ] 4.3 `PriceTag` renders a price with the currency in the muted token and the amount in the
      display face, so a price reads as a price.
- [ ] 4.4 `Skeleton`, `EmptyState`, `ErrorState`, `NotFoundState` as one family, each taking an
      illustration, a heading, a body and one action. Every locale key used is added in this
      task.
- [ ] 4.5 `Toast` for the "added to cart" confirmation, replacing the button's inline state
      change, with one polite live region owned by the provider.

## 5. Shell and pages

- [ ] 5.1 `SiteHeader`: wordmark, primary navigation, search, language switcher, cart with a
      count, account; sticky with a hairline that appears only once scrolled; mobile drawer.
- [ ] 5.2 `SiteFooter`: the seller disclosure, the payment marks, the category links, the
      language switcher. Payment marks may only appear where the disclosure provides them.
- [ ] 5.3 Home: the print-room hero band, the trust strip, category tiles, the featured grid,
      the how-it-works section and the licence FAQ.
- [ ] 5.4 Catalogue and category: the filter and sort bar, the card grid, pagination.
- [ ] 5.5 Product: the buy box above the fold as specified, the sticky action bar that appears
      only after the buy box leaves the viewport, the obligations and facts as accordions, and
      the related-goods row. Real imagery is preferred; the plate placeholder is the fallback.
- [ ] 5.6 Cart, checkout, return and account on the same components, including provider
      selection as labelled cards and the disclosure before payment.
- [ ] 5.7 Render every state of every page in every locale at 390 px and 1440 px, and record the
      screenshots as evidence with the report.

## 6. Generated imagery

- [ ] 6.1 Generate the four images specified in the identity file through Codex `image_gen`, save
      them under `storefront/public/brand/generated/`, and verify each against the palette.
- [ ] 6.2 Delete the three stock PNGs under `storefront/public/brand/` and every reference to
      them.
- [ ] 6.3 Use each generated asset only in the role the identity file assigns it, and confirm no
      surface presents a generated image as a good's own.

## 7. Retire the interim layers

- [ ] 7.1 Delete `storefront/src/lib/copy.ts` and migrate its last importers to the dictionaries.
- [ ] 7.2 Delete `storefront/src/app/shop.module.css` and the `--pb-*` bridge rules from
      `globals.css` once nothing references them.
- [ ] 7.3 Empty `LEGACY_IMPORTERS` in `storefront/scripts/check-i18n.mjs` and remove the check
      only if it has no remaining purpose; the parity check stays regardless.
- [ ] 7.4 Remove every unused component and asset the audit identified, and confirm with
      `npx tsc --noEmit`, `npm run lint` and a production build.

## 8. Verification

- [ ] 8.1 `npm --prefix storefront run lint` and `npm --prefix storefront run build`, with the
      output quoted, not summarised.
- [ ] 8.2 Re-run the full project verification sweep and confirm every blocking finding from the
      audit is closed or explicitly deferred with a reason.
- [ ] 8.3 Run `/ux-verify` against the running shop and record the screenshots at 390 px and
      1440 px in all three locales as the evidence. A passing suite is not evidence about a
      rendered page.
- [ ] 8.4 Run `/rights-verify` to confirm the publication gate is unchanged by this work, and
      state `ENGINE_VERSION` explicitly.
