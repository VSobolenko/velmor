"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CartProvider } from "@/components/CartProvider";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { Button, buttonClassName } from "@/components/ui/Button";
import { dictionaryFor, resolveLocale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

/**
 * The route error boundary. Next requires it to be a client component, and it renders inside
 * `app/layout.tsx`, which holds only `<html>` and `<body>`, so the shop chrome is rendered
 * here rather than inherited.
 *
 * A client component cannot read the `x-pb-locale` request header, so the locale is taken from
 * the first path segment: for every localised route that is the same value the header carries,
 * and a path without a locale falls back to the default.
 */
export default function Error({
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  const pathname = usePathname();
  const locale = resolveLocale(pathname.split("/")[1]);
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
      <SiteHeader locale={locale} dict={dict} />
      <main
        id="content"
        className="mx-auto flex w-full max-w-6xl flex-col items-start gap-4 px-gutter py-section"
      >
        <h1 className="font-heading text-2xl font-semibold text-ink">
          {dict["common.errorTitle"]}
        </h1>
        <p className="max-w-prose text-muted">{dict["common.errorBody"]}</p>
        <div className="flex flex-wrap gap-3">
          <Button onClick={retry}>{dict["common.retry"]}</Button>
          <Link
            className={buttonClassName("secondary", "md")}
            href={localePath(locale, "/")}
          >
            {dict["common.backToShop"]}
          </Link>
        </div>
      </main>
      <SiteFooter locale={locale} dict={dict} />
    </CartProvider>
  );
}
