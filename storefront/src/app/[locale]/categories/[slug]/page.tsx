import Link from "next/link";
import { notFound } from "next/navigation";
import { CatalogueGrid } from "@/components/CatalogueGrid";
import { CataloguePagination } from "@/components/CataloguePagination";
import { buttonClassName } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  catalogueQueryString,
  offsetFor,
  readCatalogueParams,
  type CatalogueParams,
  type RawSearchParams,
} from "@/components/catalogue-query";
import { CommerceApiError } from "@/lib/api";
import { commerceApiForServer } from "@/lib/api/server";
import type { CategoryPage as CategoryPageData } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { dictionaryFor, resolveLocale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<RawSearchParams>;
};

export default async function CategoryPage({ params, searchParams }: Props) {
  const { slug, locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const requested = readCatalogueParams(await searchParams);
  const categoryPath = `/categories/${encodeURIComponent(slug)}`;

  // Only the page is carried on a category view; there are no filters to preserve here.
  const paging: CatalogueParams = {
    q: "",
    sort: "",
    category: "",
    licence: "",
    limit: requested.limit,
    page: requested.page,
  };

  const client = await commerceApiForServer(locale);
  let category: CategoryPageData;
  try {
    category = await client.getCategory(slug, {
      limit: paging.limit,
      offset: offsetFor(paging),
    });
  } catch (error) {
    if (!(error instanceof CommerceApiError)) {
      throw error;
    }
    if (error.status === 404) {
      notFound();
    }
    return (
      <main className="mx-auto w-full max-w-6xl px-gutter py-section">
        <ErrorState
          headingLevel={1}
          title={dict["common.errorTitle"]}
          description={
            error.reason === "refusal"
              ? error.detail
              : dict["common.errorBody"]
          }
          action={
            <Link
              className={buttonClassName("secondary", "md")}
              href={localePath(
                locale,
                `${categoryPath}${catalogueQueryString(paging, paging.page)}`,
              )}
            >
              {dict["common.retry"]}
            </Link>
          }
        />
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-gutter py-section">
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-3xl font-semibold text-ink">
          {category.name}
        </h1>
        <p className="text-sm text-muted">
          {dict["catalogue.resultsLabel"]}: {formatCount(category.count, locale)}
        </p>
      </div>

      <div className="mt-8">
        {category.items.length === 0 ? (
          <EmptyState
            title={dict["catalogue.empty"]}
            description={dict["catalogue.emptyHint"]}
            action={
              <Link
                className={buttonClassName("primary", "md")}
                href={localePath(locale, "/catalogue")}
              >
                {dict["catalogue.clearFilters"]}
              </Link>
            }
          />
        ) : (
          <CatalogueGrid items={category.items} locale={locale} dict={dict} />
        )}
      </div>

      <div className="mt-8">
        <CataloguePagination
          locale={locale}
          dict={dict}
          params={paging}
          path={categoryPath}
          total={category.total}
          limit={paging.limit}
        />
      </div>
    </main>
  );
}
