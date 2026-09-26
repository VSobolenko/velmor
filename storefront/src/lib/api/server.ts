import { cookies } from "next/headers";
import { CommerceApiClient } from "./client";
import type { Locale } from "@/lib/i18n";

/**
 * A server-side client that carries the caller's session cookie.
 *
 * A `fetch` made on the Next server does not run in the browser, so the session cookie the
 * browser holds is not attached to it. It is read here with `cookies()` and sent as the
 * `Cookie` header; without that every account page would render as signed out.
 *
 * `next/headers` is a server-only module, so this file must never be imported by a client
 * component. `client.ts` stays importable from both because it does not reach for it.
 */
export async function commerceApiForServer(
  locale: Locale,
): Promise<CommerceApiClient> {
  const baseUrl = process.env.NEXT_PUBLIC_VELMOR_API_URL;
  if (baseUrl === undefined || baseUrl === "") {
    throw new Error("NEXT_PUBLIC_VELMOR_API_URL is required");
  }
  const store = await cookies();
  return CommerceApiClient.fromServer(baseUrl, locale, store.toString());
}
