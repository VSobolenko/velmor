import { headers } from "next/headers";
import { Skeleton } from "@/components/ui/Skeleton";
import { dictionaryFor, LOCALE_HEADER, resolveLocale } from "@/lib/i18n";

const PLACEHOLDERS = [1, 2, 3, 4, 5, 6, 7, 8];

/**
 * The loading state of the catalogue: the grid's own shape, in the active language, not a
 * spinner that replaces it. The placeholder blocks are hidden from assistive technology; the
 * status line is what a screen reader hears.
 */
export default async function CatalogueLoading() {
  const dict = dictionaryFor(
    resolveLocale((await headers()).get(LOCALE_HEADER)),
  );
  return (
    <main className="mx-auto w-full max-w-6xl px-gutter py-section">
      <p role="status" className="text-sm text-muted">
        {dict["catalogue.loading"]}
      </p>
      <ul className="mt-6 grid grid-cols-1 gap-gutter md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {PLACEHOLDERS.map((placeholder) => (
          <li className="flex min-w-0 flex-col gap-3" key={placeholder}>
            <Skeleton className="aspect-[4/5] w-full rounded-lg" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-6 w-1/3" />
          </li>
        ))}
      </ul>
    </main>
  );
}
