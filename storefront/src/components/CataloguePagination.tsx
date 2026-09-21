import Link from "next/link";
import { buttonClassName } from "@/components/ui/Button";
import { formatCount } from "@/lib/format";
import type { Dictionary, Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";
import {
  catalogueQueryString,
  totalPagesFor,
  type CatalogueParams,
} from "./catalogue-query";

type Props = {
  locale: Locale;
  dict: Dictionary;
  params: CatalogueParams;
  /** The route the page numbers belong to: `/catalogue` or `/categories/{slug}`. */
  path: string;
  total: number;
  limit: number;
};

/**
 * Page links carried in the address, with every active filter preserved, so a filtered page is
 * linkable and shareable. Nothing is rendered when the whole result fits on one page.
 *
 * The disabled direction is a span rather than a link to a page that does not exist; both
 * directions are real links otherwise, so they are reachable without a pointer.
 */
export function CataloguePagination({
  locale,
  dict,
  params,
  path,
  total,
  limit,
}: Props) {
  const totalPages = totalPagesFor(total, limit);
  if (totalPages <= 1) {
    return null;
  }
  const hrefFor = (page: number): string =>
    localePath(locale, `${path}${catalogueQueryString(params, page)}`);
  const current = Math.min(params.page, totalPages);

  return (
    <nav
      className="flex flex-wrap items-center justify-between gap-3"
      aria-label={dict["catalogue.pageLabel"]}
    >
      {params.page > 1 ? (
        <Link className={buttonClassName("secondary", "md")} href={hrefFor(params.page - 1)}>
          {dict["catalogue.previous"]}
        </Link>
      ) : (
        <span
          aria-disabled="true"
          className={buttonClassName("secondary", "md", "opacity-50")}
        >
          {dict["catalogue.previous"]}
        </span>
      )}

      <span className="text-sm text-muted">
        {dict["catalogue.pageLabel"]} {formatCount(current, locale)}
      </span>

      {params.page < totalPages ? (
        <Link className={buttonClassName("secondary", "md")} href={hrefFor(params.page + 1)}>
          {dict["catalogue.next"]}
        </Link>
      ) : (
        <span
          aria-disabled="true"
          className={buttonClassName("secondary", "md", "opacity-50")}
        >
          {dict["catalogue.next"]}
        </span>
      )}
    </nav>
  );
}
