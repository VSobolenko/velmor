"use client";

import { useParams } from "next/navigation";
import { DEFAULT_LOCALE, isLocale, type Locale } from "./index.ts";

/**
 * The active locale in a client component, read from the route segment. A server component
 * gets it from `params` instead and passes it down.
 *
 * Separate from `./paths.ts` so that `localePath` stays importable without Next.js.
 */
export function useLocale(): Locale {
  const params = useParams<{ locale: string }>();
  return isLocale(params.locale) ? params.locale : DEFAULT_LOCALE;
}
