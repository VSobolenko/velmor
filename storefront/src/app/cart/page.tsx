"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type CartLine, readCart } from "@/lib/cart";
import styles from "../shop.module.css";

export default function CartPage() {
  const [lines, setLines] = useState<CartLine[]>([]);

  useEffect(() => {
    setLines(readCart());
  }, []);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.brand}>
          <Link href="/">Proofbasket</Link>
        </p>
        <p className={styles.tagline}>Cart</p>
        <nav className={styles.nav}>
          <Link href="/">Home</Link>
        </nav>
      </header>
      <main className={styles.main}>
        <h1 className={styles.heading}>Cart</h1>
        {lines.length === 0 ? (
          <p className={styles.empty}>Your cart is empty.</p>
        ) : (
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
        )}
      </main>
    </div>
  );
}
