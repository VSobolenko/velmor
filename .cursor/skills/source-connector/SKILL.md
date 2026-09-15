---
name: source-connector
description: How to add or change a discovery source - the SourceSpec contract, the tier system, credential declaration, the connector ABC, and the tests a new source needs. Load when editing packages/services/src/connectors, sources, or adding an upstream.
---

# source-connector

A connector turns a query into candidates. It is read-only and says nothing about
rights: whether a candidate may be sold is decided later, by the rights engine and
the gate, for every candidate regardless of origin.

## The pieces

| File | What it owns |
|------|--------------|
| `packages/services/src/domain/source.py` | `SourceTier`, `SourceKind`, `SourceSpec` |
| `packages/services/src/sources/source_registry.py` | `DefaultSources.TABLE` (the allowlist), `SourceRegistry` |
| `packages/services/src/sources/credentials.py` | `CredentialSource` protocol |
| `packages/services/src/connectors/contract.py` | `SourceConnector` ABC - `discover(query) -> tuple[Candidate, ...]` |
| `packages/services/src/connectors/factory.py` | maps a spec to its connector |
| `packages/services/src/connectors/openverse.py` | the reference implementation |
| `packages/services/src/domain/query.py` | `SearchQuery` |

## Tiers decide what is possible

- `SourceTier.A` - per-item machine-readable rights that map to a known license.
  Machine-decidable.
- `SourceTier.B` - rights prose or a coarse license field. An agent must interpret
  it, and the interpretation must resolve to a known license before publication.
- `SourceTier.C` - no machine-readable rights. `PublicationGate` refuses tier C
  outright, so nothing from a tier C source is ever auto-published. `DefaultSources`
  deliberately contains no tier C entry.

The tier is a property of the source, not of an item. It caps what the gate will
ever allow, independently of what the resolver concludes about one item.

## Adding a source: the checklist

1. **`SourceSpec` entry** in `DefaultSources.TABLE`: `id`, `name`, `kind`,
   `tier`, `base_url`, `required_env`, `enabled`.
   - `DefaultSources.TABLE` is an **allowlist, not a starting point**. Adding a
     source widens what the platform may publish, so it is a reviewed change.
   - `required_env` is the credential contract. Name the exact environment
     variables the source needs; `SourceRegistry.validate_credentials()` refuses to
     start when an `enabled` source is missing any of them, so a half-configured
     source fails loudly instead of returning empty pages.
   - `enabled=False` while the connector does not exist. An `enabled` source always
     means "crawlable", never "declared but unimplemented".
2. **Connector** subclassing `SourceConnector`, implementing
   `async def discover(self, query: SearchQuery) -> tuple[Candidate, ...]`.
   - Return at most `query.limit` candidates.
   - Set `declared_license_id` from the source's own machine-readable field
     whenever the source reports one. That field is the provenance the auditor
     later cites; leaving it empty silently downgrades a tier A source into an
     unverifiable one.
   - Do not filter by license and do not decide publishability here.
3. **Register in the factory** so a spec id maps to the connector class.
4. **Credentials** in `packages/<agent>/.env.dev` and a placeholder (never a real
   value) in `.env.example`.
5. **Tests**: a mocked HTTP response parsed into candidates; a response with a
   missing license field; a malformed response that must raise rather than return a
   partial candidate.
6. Run `/rights-verify` - invariant 8 checks that a connector failure surfaces as a
   recorded `SourceFailure` in the run result rather than silently shrinking the
   funnel to an empty page.

## Rules

- **Verify the upstream contract before coding against it.** Read the API docs for
  the real field names, whether a field can be null, and what an error response
  looks like. `context7` and the source's own docs are there for this. Do not code
  against a half-remembered API.
- **No defensive parsing.** Validate the response into a typed model at the
  boundary. Pydantic raising on a malformed payload is the intended behaviour; do
  not catch it to return a partial object. Fail fast on empty or unexpected data.
- **No `try/except` to survive a bad response.** A connector failure is collected
  into the run report deliberately, so a broken upstream is visible. Swallowing it
  hides a silently shrinking funnel.
- **No string-built URLs with unescaped user text.** Use the client's params.
- **Respect the source's terms and rate limits.** The `httpx.AsyncClient` in
  `Container` sets a shared `User-Agent` and a 30s timeout; pass query limits
  through `SearchQuery` rather than paging until exhausted.
- A connector is I/O plus mapping. Pagination loops and retry policy belong to the
  caller, not inside `discover`.
