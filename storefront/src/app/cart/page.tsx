"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ShopChrome } from "@/components/ShopChrome";
import {
  type CartLine,
  readCart,
  removeLine,
  setLineQuantity,
} from "@/lib/cart";
import styles from "../shop.module.css";

export default function CartPage() {
  const [lines, setLines] = useState<CartLine[]>([]);

  function refresh() {
    setLines(readCart());
  }

  useEffect(() => {
    refresh();
  }, []);

  function onQuantityChange(candidateId: string, raw: string) {
    const quantity = Number.parseInt(raw, 10);
    if (Number.isNaN(quantity)) {
      return;
    }
    setLineQuantity(candidateId, quantity);
    refresh();
  }

  function onRemove(candidateId: string) {
    removeLine(candidateId);
    refresh();
  }

  return (
    <div className={styles.page}>
      <ShopChrome tagline="Cart" />
      <main className={styles.main}>
        <h1 className={styles.heading}>Cart</h1>
        {lines.length === 0 ? (
          <p className={styles.empty}>Your cart is empty.</p>
        ) : (
          <>
            <ul className={styles.list}>
              {lines.map((line) => (
                <li key={line.candidate_id} className={styles.cartLine}>
                  <Link href={`/goods/${encodeURIComponent(line.candidate_id)}`}>
                    {line.title}
                  </Link>
                  <p className={styles.meta}>
                    {line.unit_amount} {line.currency} each
                  </p>
                  <div className={styles.cartControls}>
                    <label className={styles.qtyLabel}>
                      Qty
                      <input
                        className={styles.qtyInput}
                        type="number"
                        min={1}
                        value={line.quantity}
                        onChange={(event) =>
                          onQuantityChange(
                            line.candidate_id,
                            event.target.value,
                          )
                        }
                      />
                    </label>
                    <button
                      type="button"
                      className={styles.linkButton}
                      onClick={() => onRemove(line.candidate_id)}
                    >
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            <div className={styles.actions}>
              <Link href="/checkout" className={styles.button}>
                Proceed to checkout
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
