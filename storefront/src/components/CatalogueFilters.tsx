"use client";

import { useState } from "react";
import Link from "next/link";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select, type SelectOption } from "@/components/ui/Select";
import { Sheet } from "@/components/ui/Sheet";
import type { Dictionary } from "@/lib/i18n";
import type { CatalogueFilterValues } from "./catalogue-query";

type Props = {
  dict: Dictionary;
  /** The locale-prefixed catalogue path, submitted to as a plain GET form. */
  action: string;
  /** The unfiltered catalogue, the way out of a filtered or empty view. */
  resetHref: string;
  categories: readonly SelectOption[];
  licences: readonly SelectOption[];
  values: CatalogueFilterValues;
};

/**
 * Search, sort and the category and licence filters, as one GET form.
 *
 * The address carries the state, so the form submits without JavaScript and the result is a
 * linkable view. Below `md` the category and licence selects move into the `Sheet`; the ones
 * kept hidden in the main form still submit, so a search does not silently drop the active
 * filters. The sheet holds its own form with the search term and sort carried as hidden fields
 * so applying a filter never discards them.
 */
export function CatalogueFilters({
  dict,
  action,
  resetHref,
  categories,
  licences,
  values,
}: Props) {
  const [filtersOpen, setFiltersOpen] = useState(false);

  const sortOptions: readonly SelectOption[] = [
    { value: "newest", label: dict["catalogue.sortNewest"] },
    { value: "price_asc", label: dict["catalogue.sortPriceAsc"] },
    { value: "price_desc", label: dict["catalogue.sortPriceDesc"] },
    { value: "title_asc", label: dict["catalogue.sortTitleAsc"] },
    { value: "title_desc", label: dict["catalogue.sortTitleDesc"] },
  ];

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-end"
        method="get"
        action={action}
      >
        <div className="w-full md:w-64">
          <Input
            label={dict["common.searchLabel"]}
            name="q"
            type="search"
            defaultValue={values.q}
            placeholder={dict["common.searchPlaceholder"]}
          />
        </div>

        <div className="w-full md:w-56">
          <Select
            label={dict["catalogue.sortLabel"]}
            name="sort"
            options={sortOptions}
            defaultValue={values.sort}
          />
        </div>

        <div className="hidden gap-3 md:flex md:flex-1">
          <div className="min-w-0 flex-1">
            <Select
              label={dict["catalogue.filterCategory"]}
              name="category"
              options={categories}
              defaultValue={values.category}
            />
          </div>
          <div className="min-w-0 flex-1">
            <Select
              label={dict["catalogue.filterLicence"]}
              name="license"
              options={licences}
              defaultValue={values.licence}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit">{dict["catalogue.searchSubmit"]}</Button>
          <Button
            type="button"
            variant="secondary"
            className="md:hidden"
            aria-haspopup="dialog"
            onClick={() => setFiltersOpen(true)}
          >
            {dict["catalogue.filters"]}
          </Button>
          <Link className={buttonClassName("ghost", "md")} href={resetHref}>
            {dict["catalogue.clearFilters"]}
          </Link>
        </div>
      </form>

      <Sheet
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title={dict["catalogue.filters"]}
        closeLabel={dict["common.close"]}
      >
        <form className="flex flex-col gap-4" method="get" action={action}>
          <input type="hidden" name="q" value={values.q} />
          <input type="hidden" name="sort" value={values.sort} />
          <Select
            label={dict["catalogue.filterCategory"]}
            name="category"
            options={categories}
            defaultValue={values.category}
          />
          <Select
            label={dict["catalogue.filterLicence"]}
            name="license"
            options={licences}
            defaultValue={values.licence}
          />
          <Button type="submit">{dict["catalogue.applyFilters"]}</Button>
          <Link className={buttonClassName("ghost", "md")} href={resetHref}>
            {dict["catalogue.clearFilters"]}
          </Link>
        </form>
      </Sheet>
    </div>
  );
}
