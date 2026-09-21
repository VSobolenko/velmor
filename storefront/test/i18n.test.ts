import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DEFAULT_LOCALE,
  dictionaryFor,
  isLocale,
  LOCALES,
  negotiate,
  resolveLocale,
} from "../src/lib/i18n/index.ts";
import { localePath } from "../src/lib/i18n/paths.ts";

describe("isLocale", () => {
  it("accepts a supported locale", () => {
    for (const locale of LOCALES) {
      assert.equal(isLocale(locale), true);
    }
  });

  it("rejects a region tag, an unknown language and a non-string", () => {
    assert.equal(isLocale("be-BY"), false);
    assert.equal(isLocale("de"), false);
    assert.equal(isLocale(undefined), false);
    assert.equal(isLocale(7), false);
  });
});

describe("resolveLocale", () => {
  it("returns the default for anything the route did not validate", () => {
    assert.equal(resolveLocale("de"), DEFAULT_LOCALE);
    assert.equal(resolveLocale(undefined), DEFAULT_LOCALE);
  });

  it("returns the locale it is given", () => {
    assert.equal(resolveLocale("en"), "en");
  });
});

describe("negotiate", () => {
  it("prefers the cookie over the header", () => {
    assert.equal(negotiate("en-GB,en;q=0.9", "be"), "be");
  });

  it("accepts the cookie in its request-header form", () => {
    assert.equal(negotiate(null, "pb_locale=en; other=1"), "en");
  });

  it("ignores a cookie that is not a supported locale", () => {
    assert.equal(negotiate(null, "de"), DEFAULT_LOCALE);
    assert.equal(negotiate("be", ""), "be");
  });

  it("falls back to the header when there is no cookie", () => {
    assert.equal(negotiate("be-BY,ru;q=0.8,en;q=0.5", null), "be");
    assert.equal(negotiate("en", null), "en");
  });

  it("orders by quality, not by position", () => {
    assert.equal(negotiate("ru;q=0.2,en;q=0.9", null), "en");
    assert.equal(negotiate("ru;q=0.9,en;q=0.9", null), "ru");
  });

  it("excludes a language with quality zero", () => {
    assert.equal(negotiate("be;q=0,en;q=0.5", null), "en");
  });

  it("matches on the primary subtag", () => {
    assert.equal(negotiate("en-US", null), "en");
  });

  it("returns the default when nothing is negotiable", () => {
    assert.equal(negotiate(null, null), DEFAULT_LOCALE);
    assert.equal(negotiate("de-DE,fr;q=0.7", null), DEFAULT_LOCALE);
    assert.equal(negotiate("*", null), DEFAULT_LOCALE);
  });
});

describe("dictionaryFor", () => {
  it("has a dictionary for every locale, with the brand in it", () => {
    for (const locale of LOCALES) {
      assert.equal(typeof dictionaryFor(locale)["common.brand"], "string");
    }
  });

  it("keeps ru and en apart", () => {
    assert.notEqual(
      dictionaryFor("ru")["nav.cart"],
      dictionaryFor("en")["nav.cart"],
    );
  });
});

describe("localePath", () => {
  it("prefixes a site-relative path", () => {
    assert.equal(localePath("be", "/cart"), "/be/cart");
    assert.equal(localePath("ru", "/"), "/ru");
  });

  it("keeps the query string and the fragment", () => {
    assert.equal(localePath("en", "/catalogue?q=map&page=2"), "/en/catalogue?q=map&page=2");
    assert.equal(localePath("en", "/checkout#disclosure"), "/en/checkout#disclosure");
  });

  it("replaces a locale prefix instead of stacking it", () => {
    assert.equal(localePath("be", "/ru/cart"), "/be/cart");
    assert.equal(localePath("en", "/ru/catalogue?q=1"), "/en/catalogue?q=1");
  });

  it("accepts a path without a leading slash", () => {
    assert.equal(localePath("en", "cart"), "/en/cart");
  });
});
