# Tasks

Policy note for the reviewer: **no task in this change edits the licence policy table.**
`packages/services/src/rights/license_grants.py`, `license_matrix.py`,
`publication_gate.py` and `rights_resolver.py` are read-only for this change, and
`RightsResolver.ENGINE_VERSION` does not move. This change consumes gate decisions; it does
not produce them. A task that appears to need a policy edit is a wrong task.

Ordering principle: the deterministic Python layers are complete and tested before anything
in the storefront or the deployment depends on them.

## 1. Project contract: the scoped Node exception

- [ ] 1.1 Amend `openspec/config.yaml` and `AGENTS.md` to replace "No TypeScript and no Node
  in this repository" with the scoped rule from design D1/D2: the product stays Python-only,
  `storefront/` is the single exception, and the storefront holds no rights logic and no
  payment secrets. Record the exception in the `AGENTS.md` layout and in the "Current state"
  section. This is a documented architecture-contract change and is called out for the human
  reviewer.

## 2. Python foundations: settings, models, persistence

- [ ] 2.1 Add the required settings for Saleor (API URL, app token), Stripe (secret key,
  webhook signing secret), bePaid (shop id, secret key), the storefront domain, the delivery
  link lifetime, the delivery cache size threshold and the download cache directory. Every
  setting is required and raises at bootstrap when absent; secrets are `SecretStr` and read
  at the point of use. Tests: a missing variable fails bootstrap, and a secret is not exposed
  by the settings' representation.
- [ ] 2.2 Add the domain models for a catalogue entry reference (good to Saleor product, with
  the internal link back to its `RightsRecord` and `GateDecision`), an entitlement (buyer,
  good, order, validity) and a delivery grant (short-lived authorisation). Plain typed data
  containers, no behaviour, consistent with the existing domain models. Tests pin the
  invariants those models must express.
- [ ] 2.3 Add the seller disclosure as stored domain data, not a setting (design D7), with a
  completeness check that names every missing required item. Tests cover the complete case,
  each missing item, and the naming of what is missing.
- [ ] 2.4 Persist catalogue entries, entitlements and the seller disclosure in `PostgresStore`
  and `InMemoryStore`, with the schema change. Tests exercise both stores through the shared
  contract, including the withdrawal state of a catalogue entry.

## 3. Saleor client and the publication bridge

- [ ] 3.1 Add the Saleor GraphQL client on `httpx` (design D6): product type, product and
  variant creation and update, category create and delete, and order read. Typed errors for
  transport failure, GraphQL errors and authorisation failure. Tests drive a fake transport
  for each error path.
- [ ] 3.2 Add the publication bridge (design D3): given a `GateDecision` and the source spec,
  publish, keep or withdraw, consulting `PublicationGate.listing_for`. Idempotent re-publish;
  no entry for anything not publishable; no entry for `FREE_ONLY`; withdrawal when the
  decision changes; an outcome reported for every operation including the no-ops. Tests cover
  every refusal path and every no-op, not only the happy path.
- [ ] 3.3 Add category management: create, rename, remove, and refuse to remove a category
  that still holds entries, naming the blocking entries. Assignment of a good to a category
  is read from stored mappings, so a model's suggestion is applied as data and never resolved
  at render time (design D4). Tests cover the refusal and the rename that would collide.

## 4. Goods: digest, cache and delivery

- [ ] 4.1 Add content-digest acquisition at publication and refuse to publish a good whose
  digest cannot be obtained (design D5, deny by default). Add the small-file cache with its
  configured threshold. Tests cover a successful digest, an unobtainable digest, a cache hit
  and a cache miss.
- [ ] 4.2 Add the delivery service: entitlement check, origin concealment, integrity check
  against the recorded digest, and a visible failure when the origin is unreachable, errors,
  or returns content that does not match. Nothing is recorded as delivered on failure. Tests
  use a fake origin for each failure mode and assert that no origin address appears in what
  the buyer receives.
- [ ] 4.3 Add the download endpoint: short-lived signed grant bound to the buyer, refusal of
  an expired or misused grant with a reason, and reissue from the account. Tests cover an
  entitled buyer, a grant used by the wrong buyer, an expired grant and a revoked
  entitlement.

## 5. Checkout and payment providers

- [ ] 5.1 Add the payment provider protocol and the checkout service: place an order from a
  cart, compute the exact total, and **re-verify saleability at payment time against our own
  store** (design D9) - refusing anything not `PAID_OK` and anything not publishable. Tests
  cover the `FREE_ONLY` refusal, the withdrawn-after-add-to-cart refusal, and the exact
  amount passed to the provider.
- [ ] 5.2 Add the Stripe provider in test mode, with webhook authentication and idempotent
  confirmation. Tests cover a successful payment, a failed payment leaving the order payable,
  a repeated notification changing nothing, and an unauthenticated notification being
  refused.
- [ ] 5.3 Add the bePaid provider for cards and ЕРИП through the hosted checkout, built to the
  published contract and exercised against a stub. Authentication of the notification and
  idempotency follow the same rules as 5.2. Tests cover an asynchronous ЕРИП confirmation, a
  buyer who abandons the payment page, a repeated notification, and an unauthenticated
  notification. Live credentials do not exist and are not required by this task.
- [ ] 5.4 Add refund handling: a refunded order revokes its entitlement and further downloads
  are refused with a reason. Tests cover the revocation and the refusal.
- [ ] 5.5 Add the order, cart, account and webhook endpoints to `packages/api`, wire the new
  services in `velmor/container.py`, and add the `serve` command's dependencies. Tests cover
  the endpoint behaviours specified in `commerce/checkout-payment` and the order states
  visible to the buyer and the operator.

## 6. Storefront

- [ ] 6.1 Scaffold `storefront/` as a Next.js application outside the Python workspace, with
  the lockfile committed, and a typed client for the commerce API. Confirm the Python gates
  are unaffected by its presence (`uv run ruff check`, `uv run python -m pytest packages
  velmor -q`).
- [ ] 6.2 Implement category browsing and product pages, showing the license identity and
  every obligation recorded for the good, and answering not-found for anything not in the
  catalogue.
- [ ] 6.3 Implement the cart, the account, order history, and download access from the
  account, including the unpaid order case that offers no download.
- [ ] 6.4 Implement the checkout flow: identification of the buyer, provider selection, the
  hand-off to the provider, return handling that never marks an order paid on its own, and
  the seller disclosure presented before payment with checkout unavailable while it is
  incomplete.
- [ ] 6.5 Design and branding: the shop's visual identity, category and product imagery
  generated with Codex's `image_gen` (the only image generator wired up), and the marks of
  the payment systems in use. Copy is written for a Belarusian buyer.

## 7. Deployment and end-to-end verification

- [ ] 7.1 Deploy Saleor (API, a single worker, dashboard) with hard memory limits and the
  existing `velmor-postgres` and `velmor-redis` reused as separate databases (design D11).
  Record the memory actually consumed, and confirm the other project's containers are
  untouched.
- [ ] 7.2 Add one additive site block to the existing Caddy for the storefront subdomain,
  backing up the current configuration first, validating before reload, and documenting the
  single-block rollback (design D10). Confirm the other project's sites still respond.
- [ ] 7.3 Run the publication bridge once against the 105 publishable goods and inspect the
  resulting catalogue: the count, the categories, and a spot check that no `FREE_ONLY` good
  is saleable.
- [ ] 7.4 Walk a real purchase end to end in test mode against a stubbed provider: browse,
  add to cart, pay, receive the good, re-download from the account, and confirm the origin
  address is absent from everything the buyer receives. Capture the evidence.

## 8. Documentation

- [ ] 8.1 Update the `AGENTS.md` "Current state" and roadmap sections for the commerce layer,
  and note in the change's archive summary what this adds to what Velmor may publish: nothing
  new is published by this change, and no refusal is removed.
