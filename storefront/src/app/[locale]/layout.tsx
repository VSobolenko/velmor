import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { CartProvider } from "@/components/CartProvider";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { ToastProvider } from "@/components/ui/Toast";
import { dictionaryFor, isLocale } from "@/lib/i18n";

/**
 * The locale is validated here, once: an unknown segment is a 404 and nothing below this
 * layout has to ask whether the locale is real.
 */
export async function generateMetadata({
  params,
}: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) {
    notFound();
  }
  return {
    alternates: {
      canonical: `/${locale}`,
      languages: { ru: "/ru", be: "/be", en: "/en" },
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: LayoutProps<"/[locale]"> & { children: ReactNode }) {
  const { locale } = await params;
  if (!isLocale(locale)) {
    notFound();
  }
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
      <ToastProvider
        announceLabel={dict["toast.announceLabel"]}
        regionLabel={dict["toast.regionLabel"]}
        closeLabel={dict["common.close"]}
      >
        <a
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-ink"
          href="#content"
        >
          {dict["common.skipToContent"]}
        </a>
        <SiteHeader locale={locale} dict={dict} />
        <div id="content">{children}</div>
        <SiteFooter locale={locale} dict={dict} />
      </ToastProvider>
    </CartProvider>
  );
}
