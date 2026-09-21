import Link from "next/link";
import { CatalogueFilters } from "@/components/CatalogueFilters";
import { CatalogueGrid } from "@/components/CatalogueGrid";
import { CataloguePagination } from "@/components/CataloguePagination";
import { buttonClassName } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import type { SelectOption } from "@/components/ui/Select";
import {
  CATALOGUE_MAX_LIMIT,
  CATALOGUE_SORTS,
  catalogueQueryString,
  offsetFor,
  readCatalogueParams,
  type CatalogueFilterValues,
  type CatalogueParams,
  type RawSearchParams,
} from "@/components/catalogue-query";
import {
  CommerceApiClient,
  CommerceApiError,
  type CatalogueCard,
  type CatalogueSort,
  type CategorySummary,
} from "@/lib/api";
import { formatCount } from "@/lib/format";
import { dictionaryFor, resolveLocale, type Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<RawSearchParams>;
};

type CatalogueData =
  | {
      kind: "ok";
      items: CatalogueCard[];
      total: number;
      limit: number;
      categories: CategorySummary[];
      licences: string[];
    }
  | { kind: "error"; detail: string | null };

/**
 * The distinct licence identities a buyer can filter by.
 *
 * The contract has no endpoint that lists licences, so they are read off a bounded page of the
 * catalogue. Filtering by a licence is therefore offered over the licences that are actually
 * present, never over a list invented here.
 */
function distinctLicences(items: readonly CatalogueCard[]): string[] {
  const seen = new Set<string>();
  for (const item of items) {
    if (item.license_id !== null && item.license_id !== "") {
      seen.add(item.license_id);
    }
  }
  return [...seen].sort();
}

async function loadCatalogue(
  locale: Locale,
  params: CatalogueParams,
): Promise<CatalogueData> {
  const client = CommerceApiClient.fromEnv(locale);
  const [page, categories, licenceSource] = await Promise.all([
    client.listGoods({
      q: params.q === "" ? undefined : params.q,
      sort: params.sort === "" ? undefined : (params.sort as CatalogueSort),
      category: params.category === "" ? undefined : params.category,
      license: params.licence === "" ? undefined : params.licence,
      limit: params.limit,
      offset: offsetFor(params),
    }),
    client.listCategories(),
    client.listGoods({
      category: params.category === "" ? undefined : params.category,
      limit: CATALOGUE_MAX_LIMIT,
    }),
  ]);
  return {
    kind: "ok",
    items: page.items,
    total: page.total,
    limit: page.limit,
    categories,
    licences: distinctLicences(licenceSource.items),
  };
}

export default async function CataloguePage({ params, searchParams }: Props) {
  const { locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const catalogueParams = readCatalogueParams(await searchParams);
  const cataloguePath = localePath(locale, "/catalogue");

  let data: CatalogueData;
  try {
    data = await loadCatalogue(locale, catalogueParams);
  } catch (error) {
    if (error instanceof CommerceApiError) {
      // A refusal carries a message the API wrote for a person; a validation or server fault
      // does not, and the generic localized state is shown for it instead.
      data = {
        kind: "error",
        detail: error.reason === "refusal" ? error.detail : null,
      };
    } else {
      throw error;
    }
  }

  const categories = data.kind === "ok" ? data.categories : [];
  const licences = data.kind === "ok" ? data.licences : [];

  const categoryOptions: SelectOption[] = [
    { value: "", label: dict["catalogue.allCategories"] },
    ...categories.map((category) => ({
      value: category.slug,
      label: category.name,
    })),
  ];
  const licenceOptions: SelectOption[] = [
    { value: "", label: dict["catalogue.allLicences"] },
    ...licences.map((licence) => ({ value: licence, label: licence })),
  ];
  if (catalogueParams.licence !== "" && !licences.includes(catalogueParams.licence)) {
    licenceOptions.push({
      value: catalogueParams.licence,
      label: catalogueParams.licence,
    });
  }

  const filterValues: CatalogueFilterValues = {
    q: catalogueParams.q,
    sort: (CATALOGUE_SORTS as readonly string[]).includes(catalogueParams.sort)
      ? catalogueParams.sort
      : "newest",
    // A category the catalogue does not know is left out of the select rather than shown as a
    // raw slug; the request still carries it, so the empty result is the API's answer.
    category: categoryOptions.some(
      (option) => option.value === catalogueParams.category,
    )
      ? catalogueParams.category
      : "",
    licence: catalogueParams.licence,
  };

  return (
    <main className="mx-auto w-full max-w-6xl px-gutter py-section">
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-3xl font-semibold text-ink">
          {dict["catalogue.title"]}
        </h1>
        {data.kind === "ok" ? (
          <p className="text-sm text-muted">
            {dict["catalogue.resultsLabel"]}: {formatCount(data.total, locale)}
          </p>
        ) : null}
      </div>

      <div className="mt-6">
        <CatalogueFilters
          dict={dict}
          action={cataloguePath}
          resetHref={cataloguePath}
          categories={categoryOptions}
          licences={licenceOptions}
          values={filterValues}
        />
      </div>

      <div className="mt-8">
        {data.kind === "error" ? (
          <ErrorState
            title={
              data.detail === null
                ? dict["common.errorTitle"]
                : dict["catalogue.error"]
            }
            description={data.detail ?? dict["common.errorBody"]}
            action={
              <Link
                className={buttonClassName("secondary", "md")}
                href={localePath(
                  locale,
                  `/catalogue${catalogueQueryString(catalogueParams, catalogueParams.page)}`,
                )}
              >
                {dict["common.retry"]}
              </Link>
            }
          />
        ) : data.items.length === 0 ? (
          <EmptyState
            title={dict["catalogue.empty"]}
            description={dict["catalogue.emptyHint"]}
            action={
              <Link className={buttonClassName("primary", "md")} href={cataloguePath}>
                {dict["catalogue.clearFilters"]}
              </Link>
            }
          />
        ) : (
          <CatalogueGrid items={data.items} locale={locale} dict={dict} />
        )}
      </div>

      {data.kind === "ok" ? (
        <div className="mt-8">
          <CataloguePagination
            locale={locale}
            dict={dict}
            params={catalogueParams}
            path="/catalogue"
            total={data.total}
            limit={data.limit}
          />
        </div>
      ) : null}
    </main>
  );
}
