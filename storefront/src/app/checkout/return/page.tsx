"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ShopChrome } from "@/components/ShopChrome";
import {
  CommerceApiClient,
  CommerceApiError,
  type Order,
} from "@/lib/api";
import { copy } from "@/lib/copy";
import styles from "../../shop.module.css";

const ORDER_STORAGE_KEY = "velmor.checkout.order_id";

export default function CheckoutReturnPage() {
  const [orderId, setOrderId] = useState<string | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [statusNote, setStatusNote] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.sessionStorage.getItem(ORDER_STORAGE_KEY);
    if (stored === null || stored === "") {
      setOrderId(null);
      return;
    }
    setOrderId(stored);
    const client = CommerceApiClient.fromEnv();
    client
      .getOrder(stored)
      .then((payload) => {
        setOrder(payload);
        if (payload.state === "pending") {
          setStatusNote(copy.orderPending);
        } else {
          setStatusNote(`${copy.orderState}: ${payload.state}.`);
        }
      })
      .catch((error: unknown) => {
        const detail =
          error instanceof CommerceApiError
            ? error.detail
            : error instanceof Error
              ? error.message
              : copy.couldNotLoadOrder;
        setStatusNote(detail);
      });
  }, []);

  return (
    <ShopChrome tagline={copy.paymentReturn}>
      <main className={styles.main}>
        <h1 className={styles.heading}>{copy.backFromPayment}</h1>
        <p className={styles.meta}>{copy.returnNotice}</p>
        {statusNote !== null ? <p className={styles.status}>{statusNote}</p> : null}
        <p className={styles.status}>
          <Link href="/account/orders">{copy.viewOrders}</Link>
          {orderId !== null ? (
            <>
              {" · "}
              <Link href={`/account/orders/${encodeURIComponent(orderId)}`}>
                {copy.order} {orderId}
              </Link>
            </>
          ) : null}
        </p>
        {order !== null && order.state === "paid" ? (
          <p className={styles.meta}>{copy.orderPaidDownloads}</p>
        ) : null}
      </main>
    </ShopChrome>
  );
}
