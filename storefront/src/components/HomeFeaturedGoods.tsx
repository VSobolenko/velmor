import Link from "next/link";
import { ProductCard } from "@/components/ProductCard";
import { buttonClassName } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { localePath } from "@/lib/i18n/paths";
import type { Dictionary, Locale } from "@/lib/i18n";
import type { CatalogueCard } from "@/lib/api";

type Props = {
  /** At most eight goods; the home page is a shop window, not the catalogue. */
  goods: CatalogueCard[];
  locale: Locale;
  dict: Dictionary;
};

/**
 * The identity's empty-state illustration, served as plain `<img>`: the file is already
 * optimised WebP and `next/image` would re-encode it. `EmptyState` marks the slot it is passed
 * into as `aria-hidden`, because the heading and the body carry the meaning, so it is given no
 * accessible name of its own.
 */
const EMPTY_ILLUSTRATION_SRC = "/brand/generated/empty-basket.webp";

/**
 * A bounded grid of goods as cards, with one way through to everything else.
 *
 * The cards come from `ProductCard`, so the home page and the catalogue cannot drift apart:
 * a preview, a licence badge, a format badge, a title, a size and a price next to the action,
 * with the action always visible rather than on hover.
 */
export function HomeFeaturedGoods({ goods, locale, dict }: Props) {
  return (
    <section
      aria-labelledby="home-featured-title"
      className="mx-auto max-w-6xl px-gutter pb-section"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2
          id="home-featured-title"
          className="font-heading text-2xl font-semibold text-ink"
        >
          {dict["home.featuredTitle"]}
        </h2>
        <Link
          className={buttonClassName("secondary", "sm")}
          href={localePath(locale, "/catalogue")}
        >
          {dict["home.viewAll"]}
        </Link>
      </div>
      {goods.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title={dict["home.featuredEmpty"]}
            illustration={
              // eslint-disable-next-line @next/next/no-img-element -- the asset is already optimised WebP; next/image would re-encode it
              <img
                alt=""
                className="h-24 w-24"
                decoding="async"
                height={720}
                src={EMPTY_ILLUSTRATION_SRC}
                width={720}
              />
            }
          />
        </div>
      ) : (
        <ul className="mt-6 grid gap-gutter sm:grid-cols-2 lg:grid-cols-4">
          {goods.map((card) => (
            <li key={card.candidate_id}>
              <ProductCard card={card} locale={locale} dict={dict} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
