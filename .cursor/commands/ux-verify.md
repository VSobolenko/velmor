---
name: "/ux-verify"
id: "ux-verify"
category: "Review"
description: "Buyer-surface runtime verifier — drives the running shop and proves a buyer can see, understand and buy, in every locale"
---

# /ux-verify — buyer-surface runtime verifier

Catches what no other gate in this harness can. `ruff`, `pytest` and `compileall`
prove the code is well-formed. `bugbot` and `security-review` read a diff, and a
diff cannot show that a page has no images. `/rights-verify` proves the gate still
refuses what it must, and says nothing about whether anyone can buy what it
allowed.

That gap shipped once: a complete commerce layer whose buyer surface was a list of
source filenames in one hardcoded language. Every gate passed.

This role drives the running application with a browser, looks at the result, and
reports with screenshots as evidence. It does not fix code. It hands defects to the
`/ship` fix loop.

## The invariants this command exists to prove

Every run checks the ones its impact surface touches, against the running
application, with observed results.

1. **No untranslated string.** Every page renders in `ru`, `be` and `en`; the
   dictionary parity check passes; no visible label falls back to a key name or to
   a raw source string.
2. **The locale is negotiated, and switchable from where the buyer is.** A first
   visit follows `Accept-Language`; a stored choice wins; switching on a product
   page keeps that product page. `<html lang>` matches the served locale.
3. **A visual product is shown as an image.** A catalogued good whose content is an
   image shows a preview. A good with no usable image shows a placeholder or a
   labelled cover. No broken tile and no text-only card for a visual good.
4. **The origin is never disclosed.** No buyer-facing response body or header
   contains the origin URL or a storage path.
5. **The buy box is above the fold at 390 px.** Preview, title, price, licence and
   the add-to-cart action are all inside the first viewport without scrolling.
6. **No action is hover-only, and everything is keyboard reachable with a visible
   focus ring.** Tab from the top: a good can be reached, added to the cart, and
   checkout can be reached, without a pointer.
7. **Every state is designed.** Empty, loading, error, not-found and
   partially-configured are all reachable and all explain themselves in the active
   locale.
8. **Money is formatted.** Every price carries its currency, in the locale's format.
9. **Only published goods are reachable.** A withdrawn or refused good has no
   product page and no preview, through a direct address as well as through
   browsing.

## Core principle: change-impact scope, never a fixed tour

A fixed tour misses the page next door. Derive the surface from the diff and err
toward over-covering.

### 1. Read the diff

`git diff --name-only` for uncommitted work, or `git diff <base>...HEAD --name-only`.

### 2. Classify the surface

| Changed path | Minimum sweep |
|---|---|
| `storefront/src/app/**/page.tsx` | that page, at 390 px and 1440 px, in every locale, plus invariants 1, 5, 7 |
| `storefront/src/components/**` | every page that renders the component, plus invariants 5, 6 |
| `storefront/src/lib/i18n/**` | the parity check, then home, catalogue and one product page in all three locales; invariants 1, 2 |
| `storefront/src/middleware.ts` | a bare path, a locale path, an asset path and a query string; invariant 2 |
| `storefront/src/lib/api/**` | the pages that consume the changed call; invariant 7 |
| `packages/api/**` buyer-facing routes | the DTO contract, plus invariants 4, 8, 9 |
| preview or delivery routes | invariants 3, 4, 9 with a real good: published, withdrawn, unknown, and a good with an attached cover |
| `storefront/**` styles or tokens | home, catalogue, product page at both widths; invariants 5, 6 |
| cart, checkout or account | the whole purchase walk: add, cart, checkout, return; invariants 6, 7, 8 |

When unsure whether a page is affected, include it. A false "looks fine" here is
the failure this command exists to prevent.

### 3. Write the checklist down before driving

One item per page and per invariant, with the concrete assertion. State the
uncovered items in the report rather than leaving them implied.

## Steps

### 0. Confirm the target is running

- Local: `npm --prefix storefront run build && npm --prefix storefront run start`
  (or `run dev`), against a reachable API.
- Deployed: the public URL from `AGENTS.md`.
- Record which it was, and the exact URL, in the report. A verification against
  `localhost` while the claim is about the deployment must say so.

If nothing is running, say so and report the invariants as NOT RUN. Do not
substitute reading the code for looking at the page.

### 1. Run the objective checks first

```bash
npm --prefix storefront run lint        # includes the dictionary parity check
npm --prefix storefront run build
uv run python -m pytest packages -q     # when the API or a service changed
```

Record PASS or FAIL per item with the key output line.

### 2. Drive the shop with the browser-use subagent

Dispatch exactly one `browser-use` subagent (`run_in_background: false`) with a
prompt naming:

- the base URL and the locale list,
- the exact pages in scope from the impact table,
- the two viewport widths: 390x844 and 1440x900,
- the invariants in scope, stated as things to observe and report,
- an instruction to save a screenshot per page and per width, and to report the
  absolute path of each,
- an instruction to report what it saw, not what it expected, and to stop and
  report a blocker rather than improvising around one.

Then **look at every screenshot yourself**. The subagent's description is a claim;
the image is the evidence. An invariant is only PASS if the image supports it.

Guidance for what the subagent cannot decide and you must: whether the layout reads
as a shop; whether the price is visible without scrolling; whether an image is a
real preview or a placeholder. Ask it for the DOM or a CDP measurement when a claim
is about position rather than appearance.

### 3. Exercise the concealment and reachability invariants directly

Do not verify invariant 4 or 9 by looking at a page. Fetch and inspect:

- the preview of a published good: status 200, an image `Content-Type`, and no
  origin URL in the body or in any header,
- the preview of a good that is not published, and of an unknown id: status 404,
- the product payload of a withdrawn good: 404,
- a preview whose origin no longer matches the digest: 409,
- a preview of a good whose recorded cover has lost its bytes: 500 and not 502,
  because that is our own inconsistent state and a 502 would name an upstream
  failure that did not happen and send an operator to inspect a healthy origin.

Record the observed status and a grep for the origin URL across the raw response.

### 4. Report and route

- **PASS** — every item green. State the coverage: pages driven, widths, locales,
  invariants exercised directly, and which were covered by a screenshot rather than
  by a fetch.
- **FAIL** — per failure: the page, the locale, the viewport, what was observed, and
  the screenshot path. Hand the list to the `/ship` fix loop (resume the
  implementer, scoped re-review, then re-run `/ux-verify` on the affected surface
  only).

## Limitations — state these, do not hide them

- A screenshot proves appearance at one instant in one locale. A layout that breaks
  at 768 px, or a translation that overflows at 320 px, is outside the sweep unless
  it was named in the checklist.
- Generated covers and placeholder art are judged for presence and labelling, not
  for taste. Whether the copy sells is a human judgement; report it as a
  recommendation, never as PASS.
- If the shop ran with a stub payment provider, the walk proves the UI and the
  order state transitions, not a real payment. Say so.
- Accessibility is verified structurally (focus order, target size, `aria-live`
  presence). A screen-reader pass is a separate, human-run check.

## Output

```
## UX verification

**Target:** <local url | deployed url>  **Build:** <sha or uncommitted>

### Coverage
- [PASS] home @390/1440, ru/be/en — hero, tiles, featured grid (shots: <paths>)
- [PASS] invariant 5 — buy box fully inside the first 390x844 viewport (measured)
- [FAIL] invariant 1 — catalogue card label rendered as `catalogue.licenseLabel` in be

### Not covered
- <item> — <why>

### Verdict
PASS / FAIL (N failures -> routed to fix loop)
```

## Guardrails

- Never mark an invariant PASS from reading the code. Observe it.
- Never mark it PASS from a subagent's description alone. Look at the screenshot.
- Report NOT RUN distinctly from PASS. "I could not reach the app" is not a pass.
- Do not fix code in this workflow. Report only.
- Never weaken the surface to make the sweep cheap: dropping a locale, a width or a
  page from the checklist is the failure this command exists to catch.
