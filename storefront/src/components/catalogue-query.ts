import type { CatalogueSort } from "@/lib/api";

/**
 * The catalogue query, as it travels between the address bar, the page and the API.
 *
 * The address is the state: search, sort, filters and the page live in the query string, so a
 * filtered view is linkable and shareable and the form works without JavaScript. This module
 * holds no copy and imports nothing that renders, so both the server pages and the client
 * filter form can use it.
 */

/** One page of the catalogue. */
export const CATALOGUE_PAGE_LIMIT = 24;

/** The contract fixes the API ceiling at 60; anything above it is rejected. */
export const CATALOGUE_MAX_LIMIT = 60;

/** Every sort the API accepts, in the order the select offers them. */
export const CATALOGUE_SORTS: readonly CatalogueSort[] = [
  "newest",
  "price_asc",
  "price_desc",
  "title_asc",
  "title_desc",
];

export type RawSearchParams = Record<string, string | string[] | undefined>;

export type CatalogueParams = {
  q: string;
  /**
   * Raw and deliberately unvalidated: an unrecognised sort must reach the API and come back as
   * its 422, so the page shows the error state instead of silently reordering.
   */
  sort: string;
  category: string;
  licence: string;
  limit: number;
  page: number;
};

/** What the filter form shows, which is not always what was requested. */
export type CatalogueFilterValues = {
  q: string;
  sort: string;
  category: string;
  licence: string;
};

/** A repeated parameter takes its first value; anything else is absent rather than guessed. */
function firstValue(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }
  return value ?? "";
}

function parseInteger(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

export function readCatalogueParams(
  searchParams: RawSearchParams,
): CatalogueParams {
  return {
    q: firstValue(searchParams.q).trim(),
    sort: firstValue(searchParams.sort).trim(),
    category: firstValue(searchParams.category).trim(),
    licence: firstValue(searchParams.license).trim(),
    limit: clamp(
      parseInteger(firstValue(searchParams.limit), CATALOGUE_PAGE_LIMIT),
      1,
      CATALOGUE_MAX_LIMIT,
    ),
    page: Math.max(1, parseInteger(firstValue(searchParams.page), 1)),
  };
}

/** The offset the API is asked for, derived from the page and the page size. Never negative. */
export function offsetFor(params: CatalogueParams): number {
  return Math.max(0, (params.page - 1) * params.limit);
}

export function totalPagesFor(total: number, limit: number): number {
  return Math.max(1, Math.ceil(total / limit));
}

/** The explicit query string, in a stable order, so a filtered view is linkable. */
export function catalogueQueryString(
  params: CatalogueParams,
  page: number,
): string {
  const search = new URLSearchParams();
  if (params.q !== "") {
    search.set("q", params.q);
  }
  if (params.sort !== "") {
    search.set("sort", params.sort);
  }
  if (params.category !== "") {
    search.set("category", params.category);
  }
  if (params.licence !== "") {
    search.set("license", params.licence);
  }
  if (params.limit !== CATALOGUE_PAGE_LIMIT) {
    search.set("limit", String(params.limit));
  }
  if (page > 1) {
    search.set("page", String(page));
  }
  const query = search.toString();
  return query === "" ? "" : `?${query}`;
}
