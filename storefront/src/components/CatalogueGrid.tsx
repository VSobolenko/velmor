import { ProductCard } from "@/components/ProductCard";
import type { Dictionary, Locale } from "@/lib/i18n";
import type { CatalogueCard } from "@/lib/api/types";

type Props = {
  items: readonly CatalogueCard[];
  locale: Locale;
  dict: Dictionary;
};

/**
 * The catalogue grid: a real list, so assistive technology announces how many goods it holds.
 *
 * One column at a phone width, two from `md`, three to four from `lg`. Each cell is allowed to
 * shrink, so a long unbroken title never widens the page past a 390 px viewport.
 */
export function CatalogueGrid({ items, locale, dict }: Props) {
  return (
    <ul className="grid grid-cols-1 gap-gutter md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {items.map((card) => (
        <li className="min-w-0" key={card.candidate_id}>
          <ProductCard card={card} locale={locale} dict={dict} />
        </li>
      ))}
    </ul>
  );
}
