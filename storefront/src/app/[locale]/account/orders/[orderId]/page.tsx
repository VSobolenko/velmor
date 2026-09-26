import Link from "next/link";
import { notFound } from "next/navigation";
import { accountGate } from "@/components/AccountGate";
import { DownloadButton } from "@/components/DownloadButton";
import { OrderStateBadge } from "@/components/OrderStateBadge";
import { buttonClassName } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { PriceTag } from "@/components/ui/PriceTag";
import { CommerceApiError, type CatalogueCard, type Order } from "@/lib/api";
import { commerceApiForServer } from "@/lib/api/server";
import { formatCount, formatInstant } from "@/lib/format";
import { dictionaryFor, resolveLocale, type Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ locale: string; orderId: string }>;
};

type OrderData =
  | { kind: "ok"; order: Order; titles: Map<string, string | null> }
  | { kind: "error" };

/**
 * The good's title, or `null` when it is no longer in the public catalogue.
 *
 * `_get_good` in `packages/api/src/app.py` answers `{'detail': 'good not found'}` with 404 for
 * an id the catalogue no longer publishes, exactly as on the entitlements page: a withdrawn
 * good must not turn a paid order into a failed page. Every other failure is rethrown. The
 * calls run through `Promise.allSettled` so every line is resolved in one pass and one settled
 * result is inspected without a second catch.
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

async function loadOrder(locale: Locale, orderId: string): Promise<OrderData> {
  try {
    const client = await commerceApiForServer(locale);
    const order = await client.getOrder(orderId);
    const settled = await Promise.allSettled(
      order.lines.map((line) =>
        client.getGood(encodeURIComponent(line.candidate_id)),
      ),
    );
    const titles = new Map<string, string | null>();
    order.lines.forEach((line, index) => {
      titles.set(line.candidate_id, resolvedTitle(settled[index]));
    });
    return { kind: "ok", order, titles };
  } catch (error) {
    // Documented contracts, both from `_get_order` in `packages/api/src/app.py`: an order that
    // does not exist for this buyer is a 404 and becomes the not-found page, and an API failure
    // is the order page's own `account.couldNotLoadOrder` state. Anything thrown in this process
    // instead, such as a missing build variable, is rethrown to the `error.tsx` boundary.
    if (error instanceof CommerceApiError && error.status === 404) {
      notFound();
    }
    if (!(error instanceof CommerceApiError)) {
      throw error;
    }
    return { kind: "error" };
  }
}

export default async function OrderDetailPage({ params }: Props) {
  const { orderId, locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const gate = await accountGate(locale);
  if (!gate.allowed) {
    return gate.node;
  }
  const data = await loadOrder(locale, orderId);

  if (data.kind === "error") {
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-gutter px-gutter py-section">
        <ErrorState
          headingLevel={1}
          title={dict["common.errorTitle"]}
          description={dict["account.couldNotLoadOrder"]}
          action={
            <Link
              className={buttonClassName("secondary")}
              href={localePath(
                locale,
                `/account/orders/${encodeURIComponent(orderId)}`,
              )}
            >
              {dict["common.retry"]}
            </Link>
          }
        />
        <Link
          className="tap-target inline-flex w-fit items-center text-sm font-medium text-accent-strong hover:underline"
          href={localePath(locale, "/account/orders")}
        >
          {dict["account.allOrders"]}
        </Link>
      </main>
    );
  }

  const order = data.order;
  const titles = data.titles;
  const isPaid = order.state === "paid";

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-gutter px-gutter py-section">
      <h1 className="break-words font-heading text-2xl font-semibold text-ink">
        {`${dict["account.orderTitle"]} ${order.order_id}`}
      </h1>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-muted">{dict["account.orderState"]}</span>
        <OrderStateBadge state={order.state} dict={dict} />
        <PriceTag amount={order.total} currency={order.currency} />
        <span className="text-sm text-muted">
          {formatInstant(order.created_at, locale)}
        </span>
      </div>
      <Link
        className="tap-target inline-flex w-fit items-center text-sm font-medium text-accent-strong hover:underline"
        href={localePath(locale, "/account/orders")}
      >
        {dict["account.allOrders"]}
      </Link>

      <section className="flex flex-col gap-2">
        <h2 className="font-heading text-lg font-semibold text-ink">
          {dict["account.lines"]}
        </h2>
        <Card padding="sm">
          <ul className="divide-y divide-line">
            {order.lines.map((line) => {
              const title = titles.get(line.candidate_id) ?? null;
              return (
                <li
                  key={line.candidate_id}
                  className="flex flex-wrap items-baseline justify-between gap-2 py-2"
                >
                  <Link
                    className="min-w-0 flex-1 truncate text-sm text-ink hover:underline"
                    href={localePath(
                      locale,
                      `/goods/${encodeURIComponent(line.candidate_id)}`,
                    )}
                  >
                    {title === null ? (
                      // A withdrawn good keeps its link, but the id is shown muted so it reads
                      // as an identifier rather than as the product's name.
                      <span className="text-muted">{line.candidate_id}</span>
                    ) : (
                      title
                    )}
                  </Link>
                  <span className="flex items-baseline gap-2">
                    <PriceTag
                      amount={line.unit_amount}
                      currency={order.currency}
                    />
                    <span className="text-sm text-muted">{`\u00d7 ${formatCount(line.quantity, locale)}`}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="font-heading text-lg font-semibold text-ink">
          {dict["account.downloads"]}
        </h2>
        {isPaid ? (
          <>
            <p className="text-sm text-muted">
              {dict["account.paidDownloads"]}{" "}
              <Link
                className="text-accent-strong hover:underline"
                href={localePath(locale, "/account/entitlements")}
              >
                {dict["account.entitlements"]}
              </Link>
              .
            </p>
            <ul className="flex flex-col gap-3">
              {order.lines.map((line) => {
                const title = titles.get(line.candidate_id) ?? null;
                return (
                  <li
                    key={`download-${line.candidate_id}`}
                    className="flex flex-col gap-1"
                  >
                    {title === null ? (
                      <span className="break-words text-sm text-muted">
                        {line.candidate_id}
                      </span>
                    ) : (
                      <span className="break-words text-sm text-ink">{title}</span>
                    )}
                    <DownloadButton candidateId={line.candidate_id} />
                  </li>
                );
              })}
            </ul>
          </>
        ) : (
          <p className="text-sm text-muted">{dict["account.unpaid"]}</p>
        )}
      </section>
    </main>
  );
}
