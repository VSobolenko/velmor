# Archive notes — `add-storefront-commerce`

This change does not widen what Velmor may publish: it consumes existing
`GateDecision` / `StorefrontListing` outcomes. No licence policy entry was added or
relaxed; no refusal was removed. `RightsResolver.ENGINE_VERSION` was not bumped for
policy reasons (rights tree was read-only).

Archived 2026-09-20: effect on what Velmor may publish is none - the catalogue
only consumes existing `GateDecision` / `StorefrontListing` outcomes, no licence
policy entry was added or relaxed and no refusal was removed, and
`RightsResolver.ENGINE_VERSION` did not move.

## Effect on the buyer surface

Recorded late, because this change was archived before
`.cursor/rules/07-product-surface.mdc` existed. That rule requires an archive note
to state what changed for the buyer; for this change the honest answer is the reason
the rule exists.

What shipped and worked: Saleor GraphQL publication, catalogue persistence, cart,
checkout with the seller-disclosure gate, payment providers, delivery with digest
verification and download grants, a Next.js storefront, a demo deployment reachable
at a public URL, and an end-to-end purchase walked with the stub provider.

What shipped and did not work: the entire buyer surface. The committed home page
rendered the catalogue as `<ul>` of `<Link>{good.title}</Link>` - a text list of
source filenames with a price beside each one - and `next/image` was imported on
that page and on the category page only for the brand hero and the category tiles.
No good was rendered as an image anywhere. The product page contained no image at
all: title, creator, price, licence, obligations, add-to-cart. There was no search,
no sort, no filter, no pagination and no card. The language was Belarusian,
hardcoded in `copy.ts` and in `<html lang>`, with no way to choose another. The
category section rendered its "no categories" branch, because nothing created a
category. All 26 tasks in `tasks.md` were left unticked, so that file is not a
record of completion and should not be read as one - the code, the specs and the
deploy are.

This is the failure `07-product-surface.mdc` and `/ux-verify` were written for:
every gate passed, because a diff cannot show that a page has no images and a
passing suite says nothing about a rendered page.

The surface is superseded by the `redesign-storefront-ux` change. Until that
archives, the storefront's shipped state is the one described under "Anti-patterns
seen in this repository" in `.cursor/skills/storefront-ux/SKILL.md`, not a reference
implementation.
