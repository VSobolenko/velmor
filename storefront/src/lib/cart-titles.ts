import { useEffect, useState } from "react";
import { CommerceApiClient, CommerceApiError } from "./api/client.ts";
import type { CartLine } from "@/lib/cart";
import type { Locale } from "@/lib/i18n";

export type CartTitleResolver = (candidateId: string) => Promise<string>;

type ResolvedTitles = {
  key: string;
  titles: Record<string, string>;
  fault: unknown | null;
};

function resolvedLine(
  line: CartLine,
  result: PromiseSettledResult<string>,
): CartLine {
  if (result.status === "fulfilled") {
    return { ...line, title: result.value };
  }
  if (
    result.reason instanceof CommerceApiError &&
    result.reason.status === 404 &&
    result.reason.reason === "refusal"
  ) {
    return line;
  }
  throw result.reason;
}

/** Resolves display titles through the catalogue, retaining a withdrawn good's stored snapshot. */
export async function resolveCartTitles(
  lines: CartLine[],
  resolveTitle: CartTitleResolver,
): Promise<CartLine[]> {
  const settled = await Promise.allSettled(
    lines.map((line) => resolveTitle(line.candidate_id)),
  );
  return lines.map((line, index) => resolvedLine(line, settled[index]));
}

/** Cart titles are presentation data: resolve them again whenever the buyer's locale changes. */
export function useCartTitles(
  lines: CartLine[],
  locale: Locale,
): { lines: CartLine[]; loading: boolean } {
  const key = `${locale}|${lines.map((line) => line.candidate_id).join(",")}`;
  const [resolved, setResolved] = useState<ResolvedTitles | null>(null);
  const displayLines = lines.map((line) => ({
    ...line,
    title:
      resolved?.key === key ? resolved.titles[line.candidate_id] ?? line.title : line.title,
  }));
  const loading = lines.length > 0 && resolved?.key !== key;

  useEffect(() => {
    let cancelled = false;
    const client = CommerceApiClient.fromEnv(locale);
    void resolveCartTitles(lines, async (candidateId) => {
      const good = await client.getGood(encodeURIComponent(candidateId));
      return good.title;
    })
      .then((linesWithTitles) => {
        if (!cancelled) {
          setResolved({
            key,
            titles: Object.fromEntries(
              linesWithTitles.map((line) => [line.candidate_id, line.title]),
            ),
            fault: null,
          });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setResolved({ key, titles: {}, fault: error });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [key, lines, locale]);

  if (resolved?.key === key && resolved.fault !== null) {
    throw resolved.fault;
  }
  return { lines: displayLines, loading };
}
