import Link from "next/link";
import { headers } from "next/headers";
import { CartProvider } from "@/components/CartProvider";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { buttonClassName } from "@/components/ui/Button";
import { dictionaryFor, LOCALE_HEADER, resolveLocale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

/**
 * The 404 for a request that never reached a locale segment. `src/proxy.ts` leaves a path
 * containing a dot unnegotiated, so there is no `[locale]/not-found.tsx` to render for it.
 *
 * A `not-found` boundary receives no route `params`, so the locale is read from the
 * `x-pb-locale` header the proxy sets. When it is absent the default locale is used, which is
 * the honest value for a request the shop could not localise. The chrome is rendered here
 * because the root layout holds only `<html>` and `<body>`.
 *
 * The header is told there is no session: a not-found boundary receives no route params, and a
 * 404 must not depend on the account service answering.
 */
export default async function NotFound() {
  const headerStore = await headers();
  const locale = resolveLocale(headerStore.get(LOCALE_HEADER));
  const dict = dictionaryFor(locale);

  return (
    <CartProvider
      announcements={{
        added: dict["cart.announceAdded"],
        removed: dict["cart.announceRemoved"],
        quantity: dict["cart.announceQuantity"],
        cleared: dict["cart.announceCleared"],
      }}
    >
      <a
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-ink"
        href="#content"
      >
        {dict["common.skipToContent"]}
      </a>
      <SiteHeader locale={locale} dict={dict} profile={null} />
      <main
        id="content"
        className="mx-auto flex w-full max-w-6xl flex-col items-start gap-4 px-gutter py-section"
      >
        <h1 className="font-heading text-2xl font-semibold text-ink">
          {dict["common.notFoundTitle"]}
        </h1>
        <p className="max-w-prose text-muted">{dict["common.notFoundBody"]}</p>
        <Link
          className={buttonClassName("primary", "md")}
          href={localePath(locale, "/")}
        >
          {dict["common.backToShop"]}
        </Link>
      </main>
      <SiteFooter locale={locale} dict={dict} />
    </CartProvider>
  );
}
