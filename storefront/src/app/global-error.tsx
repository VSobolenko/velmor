"use client";

import { usePathname } from "next/navigation";
import { dictionaryFor, resolveLocale } from "@/lib/i18n";

/*
 * `global-error` replaces the root layout, so neither the root layout's font variables nor the
 * design tokens from `globals.css` are guaranteed to be present: if the root layout itself is
 * what threw, the `<html>` class that carries the fonts and the stylesheet link never rendered.
 * The markup therefore brings its own document, reaches for the font token with a system
 * fallback and names no colour of its own, so it stays legible with or without the shop's
 * stylesheet. It cannot render the shared chrome for the same reason: the chrome is styled by
 * the tokens that may be missing.
 *
 * A client component cannot read the `x-pb-locale` request header, so the locale is taken from
 * the first path segment.
 */
export default function GlobalError({
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  const pathname = usePathname();
  const locale = resolveLocale(pathname.split("/")[1]);
  const dict = dictionaryFor(locale);

  return (
    <html lang={locale}>
      <body
        style={{
          fontFamily: "var(--font-sans, system-ui, sans-serif)",
          margin: 0,
          padding: "3rem 1rem",
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          gap: "1rem",
        }}
      >
        <h1 className="font-heading text-2xl font-semibold">
          {dict["common.errorTitle"]}
        </h1>
        <p>{dict["common.errorBody"]}</p>
        <button type="button" onClick={retry}>
          {dict["common.retry"]}
        </button>
      </body>
    </html>
  );
}
