import Link from "next/link";
import { accountGate } from "@/components/AccountGate";
import { DownloadButton } from "@/components/DownloadButton";
import { Badge } from "@/components/ui/Badge";
import { buttonClassName } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  CommerceApiError,
  type CatalogueCard,
  type Entitlement,
} from "@/lib/api";
import { commerceApiForServer } from "@/lib/api/server";
import { formatInstant } from "@/lib/format";
import { dictionaryFor, resolveLocale, type Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

/*
 * Per-request freshness is required: the list is the buyer's own entitlements, which change
 * when a purchase is confirmed or a right is revoked, and the page reads no cookie or header
 * that would otherwise tell Next to render it dynamically. Removing this would let the route
 * be served as a build-time snapshot of one buyer's rights.
 */
export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ locale: string }>;
};

type Row = {
  entitlement: Entitlement;
  title: string | null;
};

type EntitlementsData =
  | { kind: "ok"; rows: Row[] }
  | { kind: "error" };

/**
 * The good's title, or `null` when it is no longer in the public catalogue.
 *
 * The documented contract is a 404: `_get_good` in `packages/api/src/app.py` answers
 * `{'detail': 'good not found'}, status_code=404` when `catalogue.card` has no card for the id,
 * which is what an unpublished good looks like. Handling that one status is the display logic
 * here: withdrawing a good from the catalogue must not turn the buyer's owned entitlements into
 * a failed page. Every other failure is rethrown, so a real API fault still surfaces.
 *
 * The titles are resolved in one pass, as `account/orders/[orderId]` does: every request is
 * issued from a single `Promise.allSettled` and each settled result is inspected once, so
 * there is no per-line `await` in series and no second catch to write.
 */
function resolvedTitle(
  result: PromiseSettledResult<CatalogueCard>,
): string | null {
  if (result.status === "fulfilled") {
    return result.value.title;
  }
  if (
    result.reason instanceof CommerceApiError &&
    result.reason.status === 404
  ) {
    return null;
  }
  throw result.reason;
}

async function loadEntitlements(locale: Locale): Promise<EntitlementsData> {
  const client = await commerceApiForServer(locale);
  const entitlements = await client.listEntitlements();
  const settled = await Promise.allSettled(
    entitlements.map((entitlement) =>
      client.getGood(encodeURIComponent(entitlement.candidate_id)),
    ),
  );
  const rows = entitlements.map((entitlement, index) => ({
    entitlement,
    title: resolvedTitle(settled[index]),
  }));
  return { kind: "ok", rows };
}

export default async function EntitlementsPage({ params }: Props) {
  const { locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const gate = await accountGate(locale);
  if (!gate.allowed) {
    return gate.node;
  }

  let data: EntitlementsData;
  try {
    // `account.entitlementsUnavailable` names an API failure. A fault thrown in this process,
    // such as a missing build variable, is rethrown to the `error.tsx` boundary rather than
    // reported as a dead backend. `resolvedTitle` rethrows everything it does not own.
    data = await loadEntitlements(locale);
  } catch (error) {
    if (!(error instanceof CommerceApiError)) {
      throw error;
    }
    data = { kind: "error" };
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-gutter px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["account.entitlements"]}
      </h1>
      <Link
        className="tap-target inline-flex w-fit items-center text-sm text-muted hover:underline"
        href={localePath(locale, "/account")}
      >
        {dict["account.backToAccount"]}
      </Link>

      {data.kind === "error" ? (
        <ErrorState
          title={dict["common.errorTitle"]}
          description={dict["account.entitlementsUnavailable"]}
          action={
            <Link
              className={buttonClassName("secondary")}
              href={localePath(locale, "/account/entitlements")}
            >
              {dict["common.retry"]}
            </Link>
          }
        />
      ) : data.rows.length === 0 ? (
        <EmptyState
          title={dict["account.entitlementsEmpty"]}
          action={
            <Link
              className={buttonClassName("primary")}
              href={localePath(locale, "/catalogue")}
            >
              {dict["cart.emptyCta"]}
            </Link>
          }
        />
      ) : (
        <ul className="flex flex-col gap-gutter">
          {data.rows.map(({ entitlement, title }) => {
            const isActive = entitlement.state === "active";
            return (
              <li
                key={`${entitlement.order_id}:${entitlement.candidate_id}:${entitlement.granted_at}`}
              >
                <Card className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="min-w-0 flex-1 break-words text-sm font-medium text-ink">
                      {title === null ? entitlement.candidate_id : title}
                    </span>
                    {isActive ? null : (
                      <Badge tone="danger">{dict["account.revoked"]}</Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted">
                    {`${dict["account.granted"]} ${formatInstant(entitlement.granted_at, locale)}`}
                    {entitlement.order_id === "" ? null : (
                      <>
                        {" \u00b7 "}
                        <Link
                          className="hover:underline"
                          href={localePath(
                            locale,
                            `/account/orders/${encodeURIComponent(entitlement.order_id)}`,
                          )}
                        >
                          {`${dict["account.orderWord"]} ${entitlement.order_id}`}
                        </Link>
                      </>
                    )}
                  </p>
                  {entitlement.revocation_reason === undefined ? null : (
                    <p className="text-sm text-muted">
                      {entitlement.revocation_reason}
                    </p>
                  )}
                  {isActive ? (
                    <DownloadButton candidateId={entitlement.candidate_id} />
                  ) : (
                    <p className="text-sm text-muted">
                      {dict["account.noDownload"]}
                    </p>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
