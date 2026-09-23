# Task: stop the brand name wrapping on phones, and give the mobile cart a recognisable glyph

## Outcome

On the running storefront at viewport widths 320, 360 and 390 CSS pixels:

1. the header lays out in one row and every header child stays inside the header's own box;
2. `document.documentElement.scrollWidth <= window.innerWidth`;
3. the wordmark renders the brand name on exactly ONE line, with no wrapping and no clipping
   (`scrollWidth <= clientWidth + 1` for the wordmark and for its inner text element);
4. the cart control renders a recognisable cart or bag GLYPH together with the item count, so
   the control reads as a cart rather than as a bare number in a pill;
5. every visible header control is at least 44x44 px.

At 640 px and above the cart keeps its visible text label beside the count, and at 1024 px and
above the desktop row is unchanged.

## Measured defect - already diagnosed, do not re-investigate

Measured in the DOM on the local production build:

- At 320 px the row's content box is 273 px. The row holds: wordmark 120.4 px, cart 44 px
  (`tap-target` fixes it at `min-width: 2.75rem`), mobile cluster 96 px, plus two 8 px gaps =
  276.4 px. The row is 3.4 px short.
- The wordmark is the only shrinkable item: the cart cannot go below 44 px and the cluster is
  `shrink-0`. So the wordmark was squeezed to 117 px, and because it had no `whitespace-nowrap`
  its inner flex item shrank to `min-content` and the name BROKE ACROSS TWO LINES.
- Confirmed by measuring the text rects of the wordmark's children: `Proo` on line 1 and
  `fbasket` on line 2, the second at `top: 32`. The wordmark box was 117x64 inside a 64 px row.
- At 390 px the row is 343 px wide and the wordmark is unsqueezed at 129.4 px, one line. The
  defect is specific to the narrowest widths and is worse the narrower the viewport.

`SIZE_CLASSES.sm` in `Wordmark.tsx` is `text-2xl` and is used by `SiteHeader` only;
`SiteFooter` passes `size="md"`. So the `sm` step can be made responsive without affecting the
footer.

## Required direction

- Make the brand name unbreakable, so no future squeeze can split it.
- Create the room at 320-390 px by making the small wordmark smaller on phones and restoring
  its current size from 640 px up. `text-2xl` needs 120.4 px of the 273 px content box, which is
  what does not fit; a `text-xl` step needs about 100 px and leaves ample slack. This is the
  standard treatment and it does not touch the desktop row.
- Below 640 px, the cart shows a glyph plus the count. Draw the glyph as an inline SVG in
  `currentColor`, the way `storefront/src/components/brand/HallmarkMedallion.tsx` does it, and
  mark it `aria-hidden` because the accessible name already comes from the label and the count.
  Do not add an icon dependency and do not use a raster image.
- Do not change the mobile cluster's 8 px spacing between its two buttons, and do not reduce
  the header's horizontal gutter below 16 px.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/components/brand/Wordmark.tsx`
- `storefront/src/components/CartLink.tsx`

You may READ anything under `storefront/src/`.

You may NOT write any other file. In particular do not touch `SiteHeader.tsx`,
`MobileNav.tsx`, `globals.css`, `ui/Button.tsx`, the dictionaries, any page, or anything under
`packages/`, `velmor/`, `.cursor/`, `harness/`, `scripts/`, `openspec/`.

## Inputs to read first

- `AGENTS.md`
- `storefront/src/components/brand/Wordmark.tsx` and `brand/HallmarkMedallion.tsx`
- `storefront/src/components/CartLink.tsx`
- `storefront/src/components/SiteHeader.tsx` (read only, to see how both are placed)

## Hard rules

- Do not add a user-facing string and do not edit a dictionary. The existing `label`,
  `countLabel` and `itemCount` are the only text involved. If you need a new string, reply
  `NEEDS_KEY <dictionary.key>` and stop.
- Keep the cart's accessible name exactly as it is today: the visible-or-hidden label plus
  `countLabel`. The glyph is decoration and must not be announced.
- Keep `tap-target` on the cart and the wordmark. Do not drop the count badge.
- The glyph inherits `currentColor`; do not hardcode a colour.
- No new dependency. No `TODO`. Do not run git. Do not run a browser. Nothing that reaches the
  network.
- **Do not ask me to confirm a design and do not end with a question.** Implement the change.
  If a decision is genuinely ambiguous, pick the option that satisfies the measurements above
  and say what you picked in your reply.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run lint
npm --prefix storefront run build
```

Do not retry a failure. If a command fails, stop and report it.

## Token contract

Keep the change small and local. Reserve enough of the budget to run the three commands above.
If the work cannot be finished without dropping scope, reply exactly `CONTEXT_LIMIT` rather
than guessing or leaving a file half-edited.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
