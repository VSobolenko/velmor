import Link from "next/link";
import { accountGate } from "@/components/AccountGate";
import { OrderStateBadge } from "@/components/OrderStateBadge";
import { buttonClassName } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PriceTag } from "@/components/ui/PriceTag";
import { CommerceApiError, type Order } from "@/lib/api";
import { commerceApiForServer } from "@/lib/api/server";
import { formatInstant } from "@/lib/format";
import { dictionaryFor, resolveLocale, type Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ locale: string }>;
};

type OrdersData = { kind: "ok"; orders: Order[] } | { kind: "error" };

async function loadOrders(locale: Locale): Promise<OrdersData> {
  const client = await commerceApiForServer(locale);
  const orders = await client.listOrders();
  return { kind: "ok", orders };
}

export default async function OrdersPage({ params }: Props) {
  const { locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const gate = await accountGate(locale);
  if (!gate.allowed) {
    return gate.node;
  }

  let data: OrdersData;
  try {
    // `account.ordersUnavailable` names an API failure. A fault thrown in this process, such as
    // a missing build variable, is not a dead backend and is rethrown to the `error.tsx`
    // boundary instead of being reported as one.
    data = await loadOrders(locale);
  } catch (error) {
    if (!(error instanceof CommerceApiError)) {
      throw error;
    }
    data = { kind: "error" };
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-gutter px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["account.orders"]}
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
          description={dict["account.ordersUnavailable"]}
          action={
            <Link
              className={buttonClassName("secondary")}
              href={localePath(locale, "/account/orders")}
            >
              {dict["common.retry"]}
            </Link>
          }
        />
      ) : data.orders.length === 0 ? (
        <EmptyState
          title={dict["account.ordersEmpty"]}
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
          {data.orders.map((order) => (
            <li key={order.order_id}>
              <Card className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="min-w-0 flex-1 break-words font-heading text-base font-semibold text-ink">
                    <Link
                      className="hover:underline"
                      href={localePath(
                        locale,
                        `/account/orders/${encodeURIComponent(order.order_id)}`,
                      )}
                    >
                      {`${dict["account.orderTitle"]} ${order.order_id}`}
                    </Link>
                  </h2>
                  <OrderStateBadge state={order.state} dict={dict} />
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm text-muted">
                    {formatInstant(order.created_at, locale)}
                  </span>
                  <PriceTag amount={order.total} currency={order.currency} />
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
