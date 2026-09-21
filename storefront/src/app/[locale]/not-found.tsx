import Link from "next/link";
import { headers } from "next/headers";
import { buttonClassName } from "@/components/ui/Button";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { dictionaryFor, LOCALE_HEADER, resolveLocale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

/**
 * The not-found surface for a page under a known locale.
 *
 * A `not-found` boundary does not receive the route `params`, so the locale is read from the
 * header `src/proxy.ts` sets on every request that already carries a supported locale. A
 * request that never reached a locale renders the root `app/not-found.tsx` instead, which is
 * why this file may fall back to the default locale without lying about one.
 *
 * The panel is the same one an empty listing uses, so a mistyped URL does not land on a
 * differently shaped page than any other absence.
 */
export default async function NotFound() {
  const headerStore = await headers();
  const locale = resolveLocale(headerStore.get(LOCALE_HEADER));
  const dict = dictionaryFor(locale);

  return (
    <main className="mx-auto w-full max-w-6xl px-gutter py-section">
      <NotFoundState
        title={dict["common.notFoundTitle"]}
        description={dict["common.notFoundBody"]}
        headingLevel={1}
        action={
          <Link className={buttonClassName("primary", "md")} href={localePath(locale, "/")}>
            {dict["common.backToShop"]}
          </Link>
        }
      />
    </main>
  );
}
