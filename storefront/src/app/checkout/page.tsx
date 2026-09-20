"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ShopChrome } from "@/components/ShopChrome";
import { type CartLine, readCart } from "@/lib/cart";
import styles from "../shop.module.css";

export default function CheckoutPage() {
  const [lines, setLines] = useState<CartLine[]>([]);

  useEffect(() => {
    setLines(readCart());
  }, []);

  return (
    <div className={styles.page}>
      <ShopChrome tagline="Checkout" />
      <main className={styles.main}>
        <h1 className={styles.heading}>Checkout</h1>
        {lines.length === 0 ? (
          <p className={styles.empty}>
            Your cart is empty.{" "}
            <Link href="/">Browse the catalogue</Link>.
          </p>
        ) : (
          <>
            <ul className={styles.list}>
              {lines.map((line) => (
                <li key={line.candidate_id}>
                  <Link href={`/goods/${encodeURIComponent(line.candidate_id)}`}>
                    {line.title}
                  </Link>
                  <p className={styles.meta}>
                    {line.quantity} × {line.unit_amount} {line.currency}
                  </p>
                </li>
              ))}
            </ul>
            <div className={styles.actions}>
              <button type="button" className={styles.button} disabled>
                Pay
              </button>
            </div>
            <p className={styles.meta}>Checkout flow: task 6.4</p>
            <p className={styles.status}>
              <Link href="/cart">Back to cart</Link>
            </p>
          </>
        )}
      </main>
    </div>
  );
}
