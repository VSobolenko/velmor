"use client";

import Link from "next/link";
import { localePath } from "@/lib/i18n/paths";
import { useLocale } from "@/lib/i18n/use-locale";
import { useCart } from "./CartProvider";

type Props = {
  /**
   * The cart label. It is visible from `sm` up; below `sm` the label stays in the
   * accessibility tree while a decorative bag glyph stands in for it, so the accessible
   * name is unchanged.
   */
  label: string;
  /** The accessible name of the count, in the active locale. */
  countLabel: string;
};

/**
 * The bag glyph shown in place of the label below `sm`. It is drawn inline in `currentColor`
 * the way `brand/HallmarkMedallion` draws its mark, and it is `aria-hidden` because the link's
 * accessible name already comes from the label and the count.
 */
function CartGlyph() {
  return (
    <svg
      aria-hidden="true"
      className="shrink-0 sm:hidden"
      fill="none"
      height={16}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
      width={16}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M6 8h12v11a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2z" />
      <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    </svg>
  );
}

export function CartLink({ label, countLabel }: Props) {
  const locale = useLocale();
  const { itemCount } = useCart();
  return (
    <Link
      className="tap-target inline-flex items-center gap-1 rounded-md px-1.5 py-2 text-ink hover:bg-surface-sunken sm:px-3"
      href={localePath(locale, "/cart")}
    >
      <span className="sr-only sm:not-sr-only">{label}</span>
      <CartGlyph />
      <span className="inline-flex min-w-6 items-center justify-center rounded-pill bg-accent-soft px-1.5 py-0.5 text-xs font-semibold text-accent-strong">
        {itemCount}
      </span>
      <span className="sr-only">{countLabel}</span>
    </Link>
  );
}
