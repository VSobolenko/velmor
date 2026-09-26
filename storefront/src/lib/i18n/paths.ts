import { isLocale, type Locale } from "./index.ts";

/**
 * Prefix a site-relative path with a locale. This is the only way a link is built:
 * `localePath("be", "/cart?q=1")` is `/be/cart?q=1`.
 *
 * Idempotent: a path that already carries a supported locale has that prefix replaced, so a
 * link derived from `usePathname()` (which includes the prefix) stays correct. The query
 * string and the fragment survive.
 *
 * No Next.js import here: this is a pure function of its arguments, and it is covered by
 * `test/i18n.test.ts` under the Node test runner.
 */
export function localePath(locale: Locale, path: string): string {
  const hashAt = path.indexOf("#");
  const hash = hashAt === -1 ? "" : path.slice(hashAt);
  const withoutHash = hashAt === -1 ? path : path.slice(0, hashAt);
  const queryAt = withoutHash.indexOf("?");
  const query = queryAt === -1 ? "" : withoutHash.slice(queryAt);
  const pathname = queryAt === -1 ? withoutHash : withoutHash.slice(0, queryAt);
  const segments = pathname.split("/").filter((segment) => segment !== "");
  const rest = isLocale(segments[0]) ? segments.slice(1) : segments;
  const prefix = `/${locale}`;
  if (rest.length === 0) {
    return `${prefix}${query}${hash}`;
  }
  return `${prefix}/${rest.join("/")}${query}${hash}`;
}

/**
 * The sign-in address, carrying the path the buyer was on so a successful sign-in returns them
 * there. The `next` value is the path the caller already holds, which includes the locale.
 */
export function signInHref(locale: Locale, path: string): string {
  return `${localePath(locale, "/account/sign-in")}?next=${encodeURIComponent(path)}`;
}
