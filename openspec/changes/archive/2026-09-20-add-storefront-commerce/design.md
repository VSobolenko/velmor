## Context

See `proposal.md` for motivation. The relevant current state:

- `packages/services/src/saleor/` and `packages/services/src/payments/` exist as empty package
  placeholders; `packages/api/src/routers/` is empty. Nothing in them is in use.
- `packages/api/src/app.py` serves the current read-only catalogue page. It is replaced.
- `PublicationGate.listing_for(record)` already returns `StorefrontListing`, so the
  `PAID_OK` decision the checkout needs is available today and does not require touching the
  rights engine.
- `packages/services/src/persistence/` holds `PostgresStore` and `InMemoryStore` and the
  schema. The 105 publishable goods live there.
- `openspec/specs/` is empty, so this change creates the first main specs on archive.
- `openspec/config.yaml` and `AGENTS.md` both state "No TypeScript and no Node in this
  repository". That rule is a constraint this design must either honour or explicitly and
  narrowly amend, and the amendment is itself part of the deliverable.

Server constraints, measured: 3397 MB total memory, ~2290 MB available, 2 GB swap, 37 GB
free disk, and five unrelated containers (`backend-*`) already running. Ports 80 and 443 are
held by the other project's Caddy. The memory ceiling is the binding constraint on this
design.

## Goals / Non-Goals

**Goals:**

- A real store: categories, product pages, cart, checkout, payment, account, delivery.
- The catalogue is written only from gate decisions; there is no code path that publishes a
  good that the gate did not approve.
- A checkout that refuses to charge for anything not `PAID_OK`, enforced at payment time and
  not only at display time.
- The buyer receives the file from us and is never shown its origin.
- Two payment providers behind one abstraction, both buildable now and usable later.
- A deployment that fits the existing server without disturbing the other project.

**Non-Goals (design-level):**

- Not building a generic commerce framework. Saleor owns products, carts, orders, customers
  and the admin; we own only the rights-derived parts.
- Not implementing ERIP External. Not implementing any provider's refund API in this change;
  the refund behaviour in the specs is triggered by an operator action or a provider
  notification, not by a payment initiation.
- Not storing the whole catalogue in our object storage.
- Not adding a message broker. The existing Redis is available, but this design does not
  require a queue to satisfy any spec, so none is introduced.

## Decisions

### D1. The storefront is a Next.js application under `storefront/`

The shop needs accounts, sessions, a cart, checkout state and a responsive catalogue. Those
are the parts most expensive to build correctly from scratch and the parts the user
explicitly did not want re-invented. The reference storefront for Saleor is Next.js, so this
is also the shortest path to a working checkout.

Alternatives considered:

- **Server-rendered Python (Jinja/HTMX).** Less machinery, no Node, no rule exception. It
  means writing sessions, cart persistence, checkout state and every UI interaction by hand,
  which is precisely the "сущий ад" the user wanted to avoid.
- **A separate repository.** Keeps the rule literally intact. Rejected: two repositories and
  two deploys for one product, and one `/ship` change could no longer cover both halves.

Consequence, and it is deliberate: `openspec/config.yaml` and `AGENTS.md` gain a scoped
exception. The rule becomes "no TypeScript and no Node in the product; `storefront/` is the
single exception, and it is a presentation layer with no rights logic in it". The exception
is worded so the *product* stays Python-only and the storefront cannot become a second
place where publishing is decided.

### D2. The storefront holds no rights logic and no payment secrets

Everything that decides anything lives in Python. The storefront renders what the API gives
it and drives checkout through the API. It never talks to Saleor directly with privileged
credentials, never learns the origin address of a file, and never holds a payment provider
secret. Payment happens on the provider's page, not in our front end.

This is what keeps D1's exception narrow: the storefront is replaceable without touching a
single rights rule.

### D3. Layer placement

Per `.cursor/rules/02-architecture-layers.mdc`:

| New piece | Layer | Why there |
|---|---|---|
| Saleor GraphQL client | `packages/services` | It is an external integration. Services may import core; agents may import services. Nothing else may hold it. |
| Publication bridge | `packages/services` | It reads `GateDecision` and `PublicationGate` (both in services) and writes Saleor. It is a domain service, not an agent. |
| Payment providers | `packages/services` | Same reason: external integrations belong below the agents. |
| Entitlement and delivery-grant models | `packages/services/src/domain` | Plain typed data, consistent with the existing domain models. |
| Webhook, checkout and download endpoints | `packages/api` | They are the HTTP surface. |
| Storefront | `storefront/`, outside the Python workspace | Presentation only (D2). |
| Wiring | `velmor/container.py` | The composition root is the only place that picks concrete classes. |

The bridge and the providers are added to `packages/services`, not to a new package: the
workspace layout and the layering test in
`packages/core/tests/unit/architecture/test_layering.py` stay as they are, and no new
package is introduced for one change.

### D4. No agent is added by this change

Framework choice, per `.cursor/rules/05-agent-graphs.mdc`: **plain Python**. Every operation
here is decidable from its inputs - a decision is publishable or it is not, a payment is
confirmed or it is not, an entitlement is valid or it is not. There is no branching on
judgement, no cycle, no interrupt; LangGraph would be a straight line of calls, which rule
05 explicitly rejects. Pydantic AI and DeepAgents are not considered: there is no
extraction to make and no open-ended research to do.

A model may still *propose* a category name or a product description offline. A proposal is
data an operator or an agent applies, and once applied the mapping is a row in our database,
not a model call. A model never decides publishability, price, or delivery. This is the same
boundary the rights engine already draws between proposing evidence and ruling.

### D5. Delivery is proxy-stream with a small-file cache, not mirroring and not hotlinking

Three options were on the table:

| Option | Verdict |
|---|---|
| Mirror every file into our storage | Rejected by the user as "такое себе" for multi-gigabyte goods, and it makes us the distributor of a copy we never needed to keep. |
| Link the buyer to the origin address | Rejected: it discloses the origin, which the user explicitly does not want, and it is not delivery. |
| **Proxy-stream through us, caching only small files** | **Chosen.** The origin is never disclosed because the buyer only ever talks to us. Large goods are streamed and not retained. |

The integrity requirement in `commerce/asset-delivery` needs something to verify against, so
publication obtains a content digest for the good. If a digest cannot be obtained, the good
is not published - consistent with deny-by-default. Below a configured size the file is
cached and served from the cache; above it the file is streamed and its digest checked as it
passes. A cache miss is not an error: it means a fetch from the origin.

### D6. Saleor is reached over its GraphQL API with `httpx`, no GraphQL client dependency

Saleor exposes GraphQL, and the operations this change needs are few: create or update a
product type, create a product and variant, create and delete categories, read an order.
That is a handful of queries. A GraphQL client package would add a dependency, a code
generator and a schema-sync step for no benefit at this size.

Alternative considered: `gql` or `sgqlc` with generated types. Rejected for this change as
more machinery than the operation set justifies. If the operation set grows past a few dozen
it should be revisited, and that is recorded as a deliberate deferral.

### D7. The seller disclosure is domain data, not a setting

`AGENTS.md` and rule 04 require every setting to be present at bootstrap, with no optional
accessors, so that a half-configured process cannot start. The storefront spec requires the
opposite for the seller disclosure: checkout must be *unavailable* while an item is missing,
which means "missing" has to be a representable state rather than a startup failure.

Those two are compatible once the disclosure is not a setting. It is a row in the store,
written by an operator command, and the checkout consults it and refuses while it is
incomplete. Settings stay credentials and endpoints; content stays data. No optional
accessor is added.

### D8. Payment: one bePaid integration for cards and ЕРИП

bePaid's hosted checkout covers bank cards, Apple Pay, Google Pay, Samsung Pay and ЕРИП in a
single integration. ERIP External, where the merchant hosts the invoice logic and answers
`erip/account_verification` within 14 seconds, is more surface for the same customer-visible
result.

Decision: implement the hosted checkout path now. ERIP External is a deliberate deferral,
and would be justified only if we need to render ERIP invoices ourselves.

A payment is confirmed by the provider's notification and never by the buyer's return to the
site, because the return can be forged and the notification cannot.

### D9. The checkout re-verifies saleability at payment time against our own database

Saleor is the catalogue, but Saleor is not the authority on whether a good may be sold. If
Saleor is unreachable, synchronisation lags, or a decision is withdrawn between add-to-cart
and payment, a naive design would still charge.

Decision: at payment time the checkout reads the good's most recent decision and
`StorefrontListing` from our own store and refuses if either has changed. This makes
withdrawal effective even while the catalogue is stale, and it is what makes the
`FREE_ONLY` refusal in `commerce/checkout-payment` enforceable rather than advisory.

### D10. TLS is terminated by the existing Caddy, with one added site block

Ports 80 and 443 are held by the other project's Caddy, and two processes cannot bind the
same host port. Options:

| Option | Verdict |
|---|---|
| Run our own TLS terminator on 443 | Impossible: the port is taken. |
| Serve on a high port (e.g. `:8443`) | Rejected: payment providers review the site, and a non-standard port on the return and notification URLs is a needless obstacle. |
| **Add one site block to the existing Caddy, proxying our subdomain to our front service** | **Chosen.** |

This touches the other project's configuration, which the working rules forbid doing
carelessly. Constraints on that edit, which the implementation must honour: additive only,
existing blocks untouched, the current config backed up first, `caddy validate` before
reload, and rollback is the removal of the single added block. This is recorded here because
it is the one place this change reaches outside its own directory.

### D11. Memory budget on a shared server

Saleor API, Saleor worker, the dashboard and the storefront must fit in roughly 2.2 GB
alongside five existing containers. Decisions:

- Reuse the existing `velmor-postgres` and `velmor-redis` with separate databases and
  logical databases, rather than adding two more containers.
- Run a single Saleor worker; the extra worker types are not needed for this workload.
- Hard memory limits on every new container, so a runaway Saleor process is killed rather
  than allowed to push the host into swap and disturb the other project.
- The dashboard is deployed because an operator needs it, and it is the cheapest of the four.

Accepted failure mode: under memory pressure a new container is restarted. That is chosen
over the alternative, where the host swaps and the other project is affected.

### D12. New dependencies

| Dependency | Reason | Security note |
|---|---|---|
| `stripe` (Python) | Payment provider for the international path; the official package handles webhook signature verification, which is security-relevant and not worth hand-rolling. | Pinned version; secret key and webhook signing secret typed as `SecretStr` and read at the point of use. Test-mode keys only until the legal entity exists. |
| `httpx` (already present) | Saleor GraphQL and the bePaid API. | No new surface. Both clients send credentials only over HTTPS and never log request bodies containing a key. |
| Next.js toolchain (storefront only, outside the Python workspace) | The storefront (D1). | `npm ci` from a lockfile, versions pinned, no privileged credentials in the front end (D2). |

No other dependency is added. In particular, no GraphQL client (D6) and no queue client
(see Non-Goals).

## Risks / Trade-offs

- **Saleor does not fit the memory available** → Hard limits (D11), monitoring, and the
  fallback of splitting the stack onto a second host. This is the most likely reason this
  change has to be revisited.
- **The origin disappears or changes the file after publication** → Delivery fails visibly;
  the buyer keeps a valid entitlement (spec `commerce/asset-delivery`). Accepted: a visible
  failure is better than silently handing over a different file.
- **The origin rate-limits or blocks us at peak** → Cache below the size threshold absorbs
  the common case; streaming a large file remains a dependency on the origin. Accepted for
  now; a full mirror is the escape hatch if it becomes a real problem.
- **A lost or delayed provider notification leaves an order pending** → The buyer can retry,
  and an operator can reconcile through the dashboard. Accepted: the design never marks an
  order paid on anything but the provider's confirmation (D8).
- **Saleor is unreachable, so a withdrawn good stays visible** → The checkout re-verifies
  against our database at payment time (D9), so the stale listing cannot be sold. Accepted:
  a brief stale *display* is preferred to an empty shop.
- **Editing the other project's Caddy breaks the other site** → Additive-only edit, backup,
  validation before reload, single-block rollback (D10).
- **The `no Node` rule erodes** → The exception is scoped to `storefront/`, the storefront
  holds no rights logic and no secrets (D2), and the amendment is written down rather than
  assumed.
- **A provider's API differs from its documentation** → The bePaid path is built to the
  published contract, is exercised against a stub, and is not claimed to work against live
  credentials it does not have (proposal - Non-goals).

## Migration Plan

Deployment order, chosen so a failure at any step leaves the current shop working:

1. Settings and models; the Python layers, tested, with no deployment change.
2. Saleor deployed and reachable; the existing catalogue page still serves.
3. The publication bridge run once; the catalogue populated and inspected.
4. Storefront deployed behind the new Caddy block; the old page retired.
5. Providers wired in test mode.

Rollback: the storefront and Saleor are additive, so reverting their deployment restores the
previous surface. Our own database changes are additive tables, which are left in place.
Withdrawing every product is a single bridge operation and is the rollback for a bad
catalogue.

## Open Questions

- The exact bePaid endpoint and payload shape will be confirmed against their documentation
  at implementation time. This does not change the specs or the task breakdown: the provider
  abstraction and the notification-authentication requirement are the same either way.
- Whether the dashboard is needed at launch or can wait until an operator actually needs it.
  Deferred; it does not change any requirement.
