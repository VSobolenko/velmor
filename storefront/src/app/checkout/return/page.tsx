"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ShopChrome } from "@/components/ShopChrome";
import {
  CommerceApiClient,
  CommerceApiError,
  type Order,
} from "@/lib/api";
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
          setStatusNote("This order is still pending provider confirmation.");
        } else {
          setStatusNote(`Current order state: ${payload.state}.`);
        }
      })
      .catch((error: unknown) => {
        const detail =
          error instanceof CommerceApiError
            ? error.detail
            : error instanceof Error
              ? error.message
              : "Could not load order";
        setStatusNote(detail);
      });
  }, []);

  return (
    <div className={styles.page}>
      <ShopChrome tagline="Payment return" />
      <main className={styles.main}>
        <h1 className={styles.heading}>Back from payment</h1>
        <p className={styles.meta}>
          Payment confirmation comes from the provider. This page does not mark
          the order paid.
        </p>
        {statusNote !== null ? <p className={styles.status}>{statusNote}</p> : null}
        <p className={styles.status}>
          <Link href="/account/orders">View orders</Link>
          {orderId !== null ? (
            <>
              {" · "}
              <Link href={`/account/orders/${encodeURIComponent(orderId)}`}>
                Order {orderId}
              </Link>
            </>
          ) : null}
        </p>
        {order !== null && order.state === "paid" ? (
          <p className={styles.meta}>
            The provider already confirmed this order as paid. Downloads are on
            the order page.
          </p>
        ) : null}
      </main>
    </div>
  );
}
