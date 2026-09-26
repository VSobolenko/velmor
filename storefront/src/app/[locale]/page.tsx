import Link from "next/link";
import { HomeCategoryTiles } from "@/components/HomeCategoryTiles";
import { HomeFeaturedGoods } from "@/components/HomeFeaturedGoods";
import { HomeHero } from "@/components/HomeHero";
import { HowItWorks } from "@/components/HowItWorks";
import { LicenceFaq } from "@/components/LicenceFaq";
import { TrustStrip } from "@/components/TrustStrip";
import { buttonClassName } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  CommerceApiError,
  type CatalogueCard,
  type CategorySummary,
} from "@/lib/api";
import { commerceApiForServer } from "@/lib/api/server";
import { dictionaryFor, resolveLocale, type Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

export const dynamic = "force-dynamic";

/** The home page is a shop window: one bounded grid, not the catalogue. */
const FEATURED_LIMIT = 8;

type HomeData =
  | { kind: "ok"; categories: CategorySummary[]; goods: CatalogueCard[] }
  | { kind: "error" };

type Props = { params: Promise<{ locale: string }> };

async function loadHome(locale: Locale): Promise<HomeData> {
  const client = await commerceApiForServer(locale);
  const [categories, featured] = await Promise.all([
    client.listCategories(),
    client.listGoods({ limit: FEATURED_LIMIT }),
  ]);
  return { kind: "ok", categories, goods: featured.items };
}

export default async function Home({ params }: Props) {
  const { locale: raw } = await params;
  const locale = resolveLocale(raw);
  const dict = dictionaryFor(locale);

  let data: HomeData;
  try {
    data = await loadHome(locale);
  } catch (error) {
    // A server component cannot turn a rejected fetch into a rendered state without a catch,
    // and the API being unreachable is a state a buyer reaches, not an edge case
    // (.cursor/rules/07-product-surface.mdc, section 6). `CommerceApiError` is the client's
    // documented HTTP failure (lib/api/client.ts); the Fetch standard rejects a transport
    // failure with a `TypeError`. Everything else - a missing NEXT_PUBLIC_* variable, a
    // malformed payload - is rethrown so it fails the render loudly instead of reading as an
    // empty catalogue.
    if (error instanceof CommerceApiError || error instanceof TypeError) {
      data = { kind: "error" };
    } else {
      throw error;
    }
  }

  const goods = data.kind === "ok" ? data.goods : [];
  const categories = data.kind === "ok" ? data.categories : [];
  const heroImage = goods.length > 0 ? goods[0] : null;

  return (
    <main>
      <HomeHero image={heroImage} locale={locale} dict={dict} />
      <TrustStrip dict={dict} />
      {data.kind === "error" ? (
        <div className="mx-auto max-w-6xl px-gutter py-section">
          <EmptyState
            title={dict["common.errorTitle"]}
            description={dict["common.errorBody"]}
            action={
              <Link
                className={buttonClassName("secondary")}
                href={localePath(locale, "/")}
              >
                {dict["common.retry"]}
              </Link>
            }
          />
        </div>
      ) : (
        <>
          <HomeCategoryTiles
            categories={categories}
            goods={goods}
            locale={locale}
            dict={dict}
          />
          <HomeFeaturedGoods goods={goods} locale={locale} dict={dict} />
        </>
      )}
      <HowItWorks dict={dict} />
      <LicenceFaq dict={dict} />
    </main>
  );
}
