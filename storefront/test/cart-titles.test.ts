import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { CommerceApiError } from "../src/lib/api/client.ts";
import { resolveCartTitles } from "../src/lib/cart-titles.ts";

const line = {
  candidate_id: "openverse:good",
  unit_amount: "9.99",
  quantity: 1,
  currency: "USD",
  title: "Added in Russian",
};

describe("cart title resolution", () => {
  it("uses the active locale title and retains the snapshot only for a withdrawn-good refusal", async () => {
    const resolved = await resolveCartTitles([line], async (candidateId) => {
      assert.equal(candidateId, line.candidate_id);
      return "Title in English";
    });

    assert.equal(resolved[0].title, "Title in English");
    const withdrawn = await resolveCartTitles([line], async () => {
      throw new CommerceApiError(404, "Gone", "refusal");
    });

    assert.equal(withdrawn[0].title, line.title);

    await assert.rejects(
      resolveCartTitles([line], async () => {
        throw new CommerceApiError(503, "Unavailable", "fault");
      }),
      CommerceApiError,
    );
  });
});
