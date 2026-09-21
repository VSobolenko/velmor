import { ProductCard } from "./ProductCard";
import type { Dictionary, Locale } from "@/lib/i18n";
import type { CatalogueCard } from "@/lib/api/types";

type Props = {
  cards: CatalogueCard[];
  locale: Locale;
  dict: Dictionary;
};

/**
 * Goods from the same category, in the same card grid the catalogue uses.
 *
 * One column at 390 px: the card carries a price and an always-visible add-to-cart side by
 * side, and two of them on a 390 px row would leave neither enough room. The empty list is a
 * stated state, not a blank section.
 */
export function RelatedGoods({ cards, locale, dict }: Props) {
  return (
    <section>
      <h2 className="font-heading text-xl font-semibold text-ink">
        {dict["product.related"]}
      </h2>
      {cards.length === 0 ? (
        <p className="mt-3 text-sm text-muted">{dict["product.relatedEmpty"]}</p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-gutter sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((card) => (
            <ProductCard
              key={card.candidate_id}
              card={card}
              locale={locale}
              dict={dict}
            />
          ))}
        </div>
      )}
    </section>
  );
}
