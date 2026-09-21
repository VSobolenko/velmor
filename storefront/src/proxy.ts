import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  isLocale,
  LOCALE_COOKIE,
  LOCALE_HEADER,
  negotiate,
  type Locale,
} from "@/lib/i18n";

/**
 * Locale negotiation for every page request.
 *
 * Next 16 renamed the `middleware` file convention to `proxy` and deprecates the old name,
 * so this is `src/proxy.ts` exporting `proxy`. See
 * `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md`.
 *
 * A path that already carries a supported locale is left alone and the locale is forwarded
 * to the render tree as `x-pb-locale`. Anything else is redirected to the same path and
 * query string under the negotiated locale.
 */
export function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const segments = pathname.split("/").filter((segment) => segment !== "");
  const first = segments[0];

  if (isLocale(first)) {
    const headers = new Headers(request.headers);
    headers.set(LOCALE_HEADER, first);
    return NextResponse.next({ request: { headers } });
  }

  const cookie = request.cookies.get(LOCALE_COOKIE);
  const locale = negotiate(
    request.headers.get("accept-language"),
    cookie === undefined ? null : cookie.value,
  );

  const target = request.nextUrl.clone();
  target.pathname = pathWithLocale(pathname, locale);
  return NextResponse.redirect(target);
}

function pathWithLocale(pathname: string, locale: Locale): string {
  const prefix = `/${locale}`;
  if (pathname === "/") {
    return prefix;
  }
  return `${prefix}${pathname.startsWith("/") ? pathname : `/${pathname}`}`;
}

/**
 * Static assets, `_next`, the media proxy and any path with a file extension never reach the
 * negotiation above.
 */
export const config = {
  matcher: ["/((?!_next|media|.*\\..*).*)"],
};
