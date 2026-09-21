## Why

Velmor can decide what may legally be sold, and has nowhere to sell it. The current
Proofbasket surface is a read-only list of publishable records whose only action is a link
to the origin URL: there is no cart, no payment, no account, and the buyer never receives
the good from us. The rights work converts into no revenue, and the attribution obligations
already recorded on every `RightsRecord` are not honoured anywhere a buyer can see them.

This change builds the commerce half over the goods the gate has already approved. The gate
is not touched: it stays the only door, and this change only reads its decisions.

### The licence concern, stated explicitly

- **Which action.** Selling a download is `RightsAction.RESELL` - selling access to a copy.
  It is distinct from `REDISTRIBUTE`, and the policy table treats them separately.
- **Which evidence.** Unchanged from today. A publishable record already needs a source
  fact (`SOURCE_API_FIELD`, `LICENSE_FILE` or `HUMAN_ATTESTATION`) plus an identity match
  (`SPDX_MATCH`), a resolved license in the policy table, and an `ALLOWED` verdict.
- **What the platform refuses when evidence is missing.** No evidence, no product. A record
  that is not `GateDecision.PUBLISHABLE` has no path into the catalogue at all. The bridge
  below has no "force" and no "publish anyway".

### A gap this change must close

`PublicationGate.decide` refuses `StorefrontListing.NOT_LISTED` but does **not** refuse
`StorefrontListing.FREE_ONLY`. That is correct for the gate - a GPL good may be published -
and harmless today because no surface charges money. It stops being harmless the moment a
paid checkout exists: the policy table's own reasoning is that copyleft goods are not sold
because "a buyer free to redistribute what they paid for voids the price".

So the requirement lands on this change, not on the gate: **a paid checkout SHALL refuse any
good whose `StorefrontListing` is not `PAID_OK`.** `PublicationGate.listing_for` already
returns the listing; the commerce layer must consult it.

## What Changes

- **Saleor becomes the commerce core.** Products, categories, carts, orders and customer
  accounts come from Saleor. It is integrated behind a package under `packages/services`,
  never called from an agent node, and never asked to decide rights.
- **A publication bridge.** A deterministic service maps a `GateDecision` to a Saleor
  product: created for `PAID_OK`, absent otherwise, withdrawn when a record stops being
  publishable. This is the only writer of the catalogue.
- **A storefront.** **BREAKING** for the repository rule "No TypeScript and no Node":
  a `storefront/` Next.js application is added, with the exception documented and scoped in
  `openspec/config.yaml` and `AGENTS.md`. Categories, product pages, cart, checkout,
  account and order history.
- **Payment providers behind one abstraction.** Stripe (international) and bePaid (cards and
  ЕРИП, the Belarusian standard). Both are built now; both run against stub credentials
  until real keys exist. Nothing in the checkout path may assume a provider.
- **Delivery of the good.** On `ORDER_FULLY_PAID` our backend issues a signed, expiring
  download URL. The buyer downloads from us and is never shown the origin URL. Attribution
  obligations (author, licence, licence text) are shown on the product page and again on the
  download page, because CC-BY and CC-BY-SA require them and hiding the origin is not the
  same as hiding the author.
- **Agent-driven catalogue management.** Adding a good, creating a category and withdrawing
  a good are operations of the same bridge, so an agent can run the shop without any path
  around the gate. The operations are deterministic: a model may propose, it never rules.
- **Required seller disclosure.** The storefront carries the seller details, payment and
  return rules that the Belarusian acquirer requires of any site it processes payments for.

## Capabilities

### New Capabilities

- `commerce/catalog-publication`: how a gate decision becomes a saleable product, how the
  catalogue is withdrawn when a decision changes, and how a category is created.
- `commerce/storefront`: the customer-facing shop - category browsing, product pages,
  cart, account and order history - and the seller disclosure it must carry.
- `commerce/checkout-payment`: placing an order, the provider abstraction, the Stripe and
  bePaid paths, and the refusal of anything not `PAID_OK`.
- `commerce/asset-delivery`: what a buyer receives after payment, how the download link is
  authorised and expires, and how attribution is preserved.

### Modified Capabilities

None. `openspec/specs/` is empty, and this change alters no existing requirement: the gate,
the matrix, the connectors and the auditor keep their contracts.

## Non-goals

- **No change to the rights engine.** `license_grants.py`, `license_matrix.py`,
  `publication_gate.py` and `rights_resolver.py` are not edited. `ENGINE_VERSION` does not
  move, because no verdict can change for identical inputs: this change consumes decisions.
- **No new sources.** Wikimedia Commons stays disabled; discovery and screening are out of
  scope.
- **No real credentials.** No live Stripe or bePaid key is added. Real payments also need a
  registered legal entity and a Torgovyy reestr entry, which do not exist yet.
- **No physical shipping.** Every good here is a file. There is no address, no carrier and
  no fulfillment for anything that ships.
- **No second storefront.** The existing Python catalogue page is replaced, not kept
  alongside under a flag.
- **No human dashboard beyond Saleor's own admin**, which is deployed, not built.
- **No new discovery or audit work.** The 105 already-approved goods are the working set.

## Impact

**Code**

- `packages/services/src/saleor/` - currently an empty placeholder; gains the GraphQL client
  and the publication bridge.
- `packages/services/src/payments/` - currently an empty placeholder; gains the provider
  abstraction and the Stripe and bePaid providers.
- `packages/api/` - the existing catalogue page and its routes are replaced; webhook
  endpoints for both providers and the download endpoint are added.
- `storefront/` - new Next.js application.
- `packages/services/src/domain/` - new models for an order entitlement and a delivery
  grant. No existing model changes.
- `velmor/` - CLI gains the commands that publish, withdraw and serve; the container wires
  the new services.

**Dependencies**

- New: a Saleor GraphQL client, a Stripe client, and the Next.js toolchain under
  `storefront/`. Each needs a stated reason and a security note in `design.md`.
- Unchanged: no version moved in the Python workspace unless a client forces it.

**Systems**

- New services on the server: Saleor API, Saleor worker, Saleor dashboard, and the
  storefront. The memory budget is the binding constraint and is addressed in `design.md`.
- New public HTTPS surface: provider webhooks and the download endpoint are called from
  outside, so a domain and TLS are prerequisites, not preferences.
- Reused: the existing `velmor-postgres` and `velmor-redis` serve Saleor as separate
  databases rather than new containers.

**Risk**

- The catalogue becomes writable by a service for the first time. Every protection is in
  that service reading gate decisions and in the checkout refusing anything not `PAID_OK`.
- Real payment cannot be completed before the legal entity exists, so this change ships
  verifiable in test mode only. That limit is stated here so it is not mistaken later for a
  working income path.
