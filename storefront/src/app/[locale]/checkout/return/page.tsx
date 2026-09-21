"use client";

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import { OrderStateBadge } from "@/components/OrderStateBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { CommerceApiClient, type Order } from "@/lib/api";
import { dictionaryFor } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";
import { useLocale } from "@/lib/i18n/use-locale";

const ORDER_STORAGE_KEY = "velmor.checkout.order_id";

/**
 * The order the return page is about: `order_id` on the provider's return URL, falling back to
 * the id the checkout page stored before handing the buyer to the provider.
 */
function readOrderId(): string | null {
  const fromQuery = new URLSearchParams(window.location.search).get("order_id");
  if (fromQuery !== null && fromQuery !== "") {
    return fromQuery;
  }
  const stored = window.sessionStorage.getItem(ORDER_STORAGE_KEY);
  return stored === null || stored === "" ? null : stored;
}

/**
 * A stable no-op: the query string and the tab's storage do not change while this page is open.
 * The reader is still the correct way to reach them, because a `setState` in an effect body
 * would cascade a render.
 */
function subscribeToOrderId(): () => void {
  return () => {};
}

/** The server render has no location: `null` is the honest value before hydration. */
function noOrderId(): string | null {
  return null;
}

export default function CheckoutReturnPage() {
  const locale = useLocale();
  const dict = dictionaryFor(locale);
  const orderId = useSyncExternalStore(
    subscribeToOrderId,
    readOrderId,
    noOrderId,
  );
  const [order, setOrder] = useState<Order | null>(null);
  const [failed, setFailed] = useState(false);
  /* Bumped by the retry control to re-run the order fetch without a page reload. */
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (orderId === null) {
      return;
    }
    let cancelled = false;
    const client = CommerceApiClient.fromEnv(locale);
    client
      .getOrder(orderId)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setOrder(payload);
        setFailed(false);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [locale, orderId, attempt]);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-gutter px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["checkout.returnTitle"]}
      </h1>
      <p className="max-w-prose text-sm text-muted">
        {dict["checkout.returnNotice"]}
      </p>

      {orderId === null ? null : failed ? (
        <ErrorState
          title={dict["common.errorTitle"]}
          description={dict["account.couldNotLoadOrder"]}
          action={
            <Button
              variant="secondary"
              size="md"
              onClick={() => {
                setOrder(null);
                setFailed(false);
                setAttempt((current) => current + 1);
              }}
            >
              {dict["common.retry"]}
            </Button>
          }
        />
      ) : order === null ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <Card className="flex flex-col gap-3">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted">
              {dict["checkout.returnStateLabel"]}
            </span>
            <OrderStateBadge state={order.state} dict={dict} />
          </p>
          <p className="break-words text-sm text-ink">
            {`${dict["checkout.returnOrderLabel"]} ${order.order_id}`}
          </p>
          {order.state === "pending" ? (
            <p className="text-sm text-ink">{dict["checkout.returnPending"]}</p>
          ) : null}
          {order.state === "paid" ? (
            <p className="text-sm text-ink">{dict["checkout.returnPaidNote"]}</p>
          ) : null}
        </Card>
      )}

      <Link
        className="tap-target inline-flex w-fit items-center text-sm font-medium text-accent-strong hover:underline"
        href={localePath(locale, "/account/orders")}
      >
        {dict["checkout.returnViewOrders"]}
      </Link>
    </main>
  );
}
