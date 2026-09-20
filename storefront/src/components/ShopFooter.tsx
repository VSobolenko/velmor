"use client";

import { useEffect, useState } from "react";
import {
  CommerceApiClient,
  CommerceApiError,
} from "@/lib/api";
import styles from "@/app/shop.module.css";
import { PaymentMarks } from "./PaymentMarks";

const FALLBACK_MARKS = ["Stripe", "bePaid", "ЕРІП"];

/** Site-wide footer: payment marks from disclosure, or safe text fallbacks. */
export function ShopFooter() {
  const [marks, setMarks] = useState<string[]>(FALLBACK_MARKS);

  useEffect(() => {
    const client = CommerceApiClient.fromEnv();
    client
      .getCheckoutDisclosure()
      .then((payload) => {
        const fromDisclosure = payload.disclosure.payment_system_marks;
        if (fromDisclosure.length > 0) {
          setMarks(fromDisclosure);
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof CommerceApiError) && !(error instanceof Error)) {
          return;
        }
        // Keep fallback marks when disclosure is unreachable.
      });
  }, []);

  return (
    <footer className={styles.footer}>
      <p className={styles.footerBrand}>Proofbasket</p>
      <PaymentMarks marks={marks} labelled />
    </footer>
  );
}
