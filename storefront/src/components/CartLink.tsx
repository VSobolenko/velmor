"use client";

import Link from "next/link";
import { localePath } from "@/lib/i18n/paths";
import { useLocale } from "@/lib/i18n/use-locale";
import { useCart } from "./CartProvider";

type Props = {
  /** The visible cart label. */
  label: string;
  /** The accessible name of the count, in the active locale. */
  countLabel: string;
};

export function CartLink({ label, countLabel }: Props) {
  const locale = useLocale();
  const { itemCount } = useCart();
  return (
    <Link
      className="tap-target inline-flex items-center gap-1 rounded-md px-3 py-2 text-ink hover:bg-surface-sunken"
      href={localePath(locale, "/cart")}
    >
      <span>{label}</span>
      <span className="inline-flex min-w-6 items-center justify-center rounded-pill bg-accent-soft px-1.5 py-0.5 text-xs font-semibold text-accent-strong">
        {itemCount}
      </span>
      <span className="sr-only">{countLabel}</span>
    </Link>
  );
}
