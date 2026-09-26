import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import { CommerceApiClient } from "../src/lib/api/client.ts";

/*
 * The product page is where a buyer buys, and it answered 404 for every good: nothing could be
 * bought at all.
 *
 * A `[candidateId]` route segment reaches a `page.tsx` undecoded while a `route.ts` receives it
 * decoded (vercel/next.js#64952, "pathParam is undecoded when used from page.tsx and useParams()
 * but is decoded when used from route.ts"). The product page therefore already holds
 * `openverse%3A...`, and encoding that a second time sent `openverse%253A...`, which the API
 * answers with 404.
 *
 * These tests pin the contract where it broke: the client places the value it is given as a path
 * segment and does not encode it again. A caller holding a raw id from API JSON, as the account
 * pages do, makes it a segment with `encodeURIComponent` itself, which the second test pins.
 */

const SEGMENT = "openverse%3A0ccdd09f-d9c2-4aef-ba85-12a8ca214b66";
const RAW_ID = "openverse:0ccdd09f-d9c2-4aef-ba85-12a8ca214b66";

const originalFetch = globalThis.fetch;
const requested: string[] = [];

function stubFetch(): void {
  requested.length = 0;
  globalThis.fetch = (async (input: unknown) => {
    requested.push(String(input));
    return new Response("{}", {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof globalThis.fetch;
}

const SESSION_COOKIE = "velmor_session=0ccdd09f-d9c2-4aef-ba85-12a8ca214b66";

function client(): CommerceApiClient {
  return CommerceApiClient.fromServer("https://api.example", "en", SESSION_COOKIE);
}

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("the catalogue request path", () => {
  it("does not encode a route segment a second time", async () => {
    stubFetch();

    await client().getGood(SEGMENT);

    assert.equal(requested.length, 1);
    assert.ok(
      requested[0].includes(`/catalogue/goods/${SEGMENT}`),
      `the segment must be sent as given, got ${requested[0]}`,
    );
    assert.ok(
      !requested[0].includes("%253A"),
      `the id must not be encoded twice, got ${requested[0]}`,
    );
  });

  it("reaches the same path from a raw id once the caller encodes it", async () => {
    stubFetch();

    await client().getGood(encodeURIComponent(RAW_ID));

    assert.ok(
      requested[0].includes(`/catalogue/goods/${SEGMENT}`),
      `a raw id must arrive encoded once, got ${requested[0]}`,
    );
  });

  it("still sends the locale, which the API never negotiates for itself", async () => {
    stubFetch();

    await client().getGood(SEGMENT);

    assert.ok(
      requested[0].endsWith("?locale=en"),
      `expected the locale on the request, got ${requested[0]}`,
    );
  });

  it("never sends a buyer-identifying header", async () => {
    let headers: Headers | undefined;
    globalThis.fetch = (async (_input: unknown, init?: RequestInit) => {
      headers = new Headers(init?.headers);
      return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
    }) as typeof globalThis.fetch;

    await client().listOrders();

    assert.equal(headers?.has("X-Buyer-Id"), false);
  });
});

/*
 * The session is the only thing that identifies a buyer now that the `X-Buyer-Id` header is gone,
 * so the cookie is the whole authentication. A request made on the Next server does not run in
 * the browser and carries no cookie of its own, so the client has to attach the one the caller
 * sent; a request made in the browser must instead use the shop's own origin, where the cookie
 * the API set travels first-party and automatically. An account page that always looked
 * unauthenticated is exactly the failure this pins.
 */
describe("the session a request is authenticated with", () => {
  it("attaches the caller's cookie to a server-side request", async () => {
    let headers: Headers | undefined;
    globalThis.fetch = (async (_input: unknown, init?: RequestInit) => {
      headers = new Headers(init?.headers);
      return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
    }) as typeof globalThis.fetch;

    await client().listOrders();

    assert.equal(headers?.get("Cookie"), SESSION_COOKIE);
  });

  it("keeps a browser-side request on the shop's own origin", async () => {
    stubFetch();

    await CommerceApiClient.fromEnv("en").listOrders();

    assert.equal(requested[0], "/api/account/orders");
  });
});
