import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatCount } from "@/lib/format";
import { localePath } from "@/lib/i18n/paths";
import { previewSrc } from "@/lib/media";
import type { Dictionary, Locale } from "@/lib/i18n";
import type { CatalogueCard, CategorySummary } from "@/lib/api";

type Props = {
  categories: CategorySummary[];
  /** The featured goods, searched for a representative image per category. */
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
 * Category tiles so a visitor self-sorts instead of paging the whole catalogue.
 *
 * Each tile carries a real image of a good in that category. A category with no published good
 * in the featured set gets a neutral surface block, never a broken image and never a text-only
 * tile: this surface exists to show goods, and an image-less tile repeats the failure it was
 * rebuilt to remove.
 */
export function HomeCategoryTiles({ categories, goods, locale, dict }: Props) {
  return (
    <section
      aria-labelledby="home-categories-title"
      className="mx-auto max-w-6xl px-gutter py-section"
    >
      <h2
        id="home-categories-title"
        className="font-heading text-2xl font-semibold text-ink"
      >
        {dict["home.categoriesTitle"]}
      </h2>
      {categories.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title={dict["home.categoriesEmpty"]}
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
          {categories.map((category) => {
            const representative = goods.find(
              (good) => good.category_slug === category.slug,
            );
            return (
              <li key={category.category_id}>
                <Link
                  className="group block"
                  href={localePath(locale, `/categories/${category.slug}`)}
                >
                  <Card
                    padding="none"
                    className="overflow-hidden transition-shadow duration-base ease-standard hover:shadow-md"
                  >
                    <div className="relative aspect-video overflow-hidden bg-surface-sunken">
                      {representative === undefined ? (
                        <div
                          aria-hidden="true"
                          className="h-full w-full bg-surface-sunken"
                        />
                      ) : (
                        // eslint-disable-next-line @next/next/no-img-element -- the API serves an already optimised WebP; next/image would re-encode it
                        <img
                          className="h-full w-full object-cover transition-transform duration-base ease-standard group-hover:scale-[1.03]"
                          src={previewSrc(representative.candidate_id)}
                          alt={category.name}
                          loading="lazy"
                          decoding="async"
                        />
                      )}
                    </div>
                    <div className="flex items-center justify-between gap-3 p-4">
                      <span className="font-heading text-base font-semibold text-ink">
                        {category.name}
                      </span>
                      <span className="text-sm text-muted">
                        {formatCount(category.count, locale)}
                      </span>
                    </div>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
