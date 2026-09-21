import type { Metadata } from "next";
import { headers } from "next/headers";
import { Inter, Playfair_Display } from "next/font/google";
import type { ReactNode } from "react";
import { dictionaryFor, LOCALE_HEADER, resolveLocale } from "@/lib/i18n";
import "./globals.css";

/*
 * The print-room pairing: an editorial serif for display, a neutral sans for everything
 * read at length or at small size.
 *
 * Both were verified to carry the locales this shop serves before being chosen, by reading
 * the `unicode-range` of the subset Google Fonts returns. Playfair Display's cyrillic subset
 * is `U+0400-045F`, which covers the Belarusian ў (U+045E) and і (U+0456) as well as Russian;
 * it offers no `cyrillic-ext`, so requesting one would fail the build rather than degrade.
 * Inter offers the extended range and takes it.
 */
const inter = Inter({
  variable: "--font-body",
  subsets: ["latin", "cyrillic", "cyrillic-ext"],
});

const playfairDisplay = Playfair_Display({
  variable: "--font-display",
  subsets: ["latin", "cyrillic"],
});

/**
 * Absolute origin for the URL-based metadata fields (`alternates`, `openGraph`). The public
 * hostname is only known per request: the API host and the shop host differ in every
 * deployment, and the proxy sets `x-forwarded-proto`.
 */
function siteOrigin(requestHeaders: Headers): URL {
  const host = requestHeaders.get("host");
  if (host === null || host === "") {
    throw new Error("The Host header is required to build absolute metadata URLs");
  }
  const protocol = requestHeaders.get("x-forwarded-proto") ?? "http";
  return new URL(`${protocol}://${host}`);
}

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const dict = dictionaryFor(resolveLocale(requestHeaders.get(LOCALE_HEADER)));
  return {
    metadataBase: siteOrigin(requestHeaders),
    title: {
      default: dict["common.brand"],
      template: `%s | ${dict["common.brand"]}`,
    },
    description: dict["footer.tagline"],
  };
}

export default async function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const locale = resolveLocale((await headers()).get(LOCALE_HEADER));
  return (
    <html lang={locale} className={`${inter.variable} ${playfairDisplay.variable}`}>
      <body>{children}</body>
    </html>
  );
}
