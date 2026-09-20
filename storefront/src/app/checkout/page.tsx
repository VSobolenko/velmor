"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ShopChrome } from "@/components/ShopChrome";
import {
  CommerceApiClient,
  CommerceApiError,
  type CheckoutDisclosureResponse,
} from "@/lib/api";
import { type CartLine, readCart } from "@/lib/cart";
import styles from "../shop.module.css";

const ORDER_STORAGE_KEY = "velmor.checkout.order_id";

type ProviderId = "stripe" | "bepaid";

const PROVIDERS: { id: ProviderId; label: string }[] = [
  { id: "stripe", label: "Stripe" },
  { id: "bepaid", label: "bePaid (card / ERIP)" },
];

const DISCLOSURE_FIELDS: {
  key: keyof CheckoutDisclosureResponse["disclosure"];
  label: string;
}[] = [
  { key: "legal_name", label: "Legal name" },
  { key: "registration_number", label: "Registration number" },
  { key: "registration_date", label: "Registration date" },
  { key: "registration_authority", label: "Registration authority" },
  { key: "shop_register_number", label: "Shop register number" },
  { key: "postal_address", label: "Postal address" },
  { key: "working_hours", label: "Working hours" },
  { key: "contact_details", label: "Contact details" },
  { key: "payment_rules", label: "Payment rules" },
  { key: "return_rules", label: "Return rules" },
  { key: "payment_system_marks", label: "Payment system marks" },
];

function formatField(
  key: keyof CheckoutDisclosureResponse["disclosure"],
  disclosure: CheckoutDisclosureResponse["disclosure"],
): string {
  const value = disclosure[key];
  if (key === "payment_system_marks") {
    return (value as string[]).join(", ");
  }
  if (value === null) {
    return "";
  }
  return String(value);
}

function cartCurrency(lines: CartLine[]): string | null {
  if (lines.length === 0) {
    return null;
  }
  const currencies = new Set(lines.map((line) => line.currency));
  if (currencies.size !== 1) {
    return null;
  }
  return lines[0].currency;
}

export default function CheckoutPage() {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [disclosure, setDisclosure] = useState<CheckoutDisclosureResponse | null>(
    null,
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [providerId, setProviderId] = useState<ProviderId>("stripe");
  const [payError, setPayError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [clientReady, setClientReady] = useState(false);

  useEffect(() => {
    setLines(readCart());
    setClientReady(true);
    const client = CommerceApiClient.fromEnv();
    client
      .getCheckoutDisclosure()
      .then((payload) => {
        setDisclosure(payload);
        setLoadError(null);
      })
      .catch((error: unknown) => {
        const detail =
          error instanceof CommerceApiError
            ? error.detail
            : error instanceof Error
              ? error.message
              : "Failed to load seller disclosure";
        setLoadError(detail);
      });
  }, []);

  async function onPay() {
    setPayError(null);
    const currency = cartCurrency(lines);
    if (currency === null) {
      setPayError("Cart lines must share one currency.");
      return;
    }
    if (disclosure === null || !disclosure.complete) {
      setPayError("Checkout is unavailable until seller disclosure is complete.");
      return;
    }
    setPaying(true);
    const client = CommerceApiClient.fromEnv();
    const returnUrl = `${window.location.origin}/checkout/return`;
    try {
      const started = await client.startCheckout({
        provider_id: providerId,
        return_url: returnUrl,
        currency,
        lines: lines.map((line) => ({
          candidate_id: line.candidate_id,
          unit_amount: line.unit_amount,
          quantity: line.quantity,
        })),
      });
      window.sessionStorage.setItem(ORDER_STORAGE_KEY, started.order_id);
      window.location.assign(started.redirect_url);
    } catch (error: unknown) {
      const detail =
        error instanceof CommerceApiError
          ? error.detail
          : error instanceof Error
            ? error.message
            : "Checkout failed";
      setPayError(detail);
      setPaying(false);
    }
  }

  const currency = cartCurrency(lines);
  const canPay =
    disclosure !== null &&
    disclosure.complete &&
    currency !== null &&
    !paying &&
    loadError === null;

  return (
    <div className={styles.page}>
      <ShopChrome tagline="Checkout" />
      <main className={styles.main}>
        <h1 className={styles.heading}>Checkout</h1>
        {!clientReady ? (
          <p className={styles.meta}>Loading…</p>
        ) : lines.length === 0 ? (
          <p className={styles.empty}>
            Your cart is empty. <Link href="/">Browse the catalogue</Link>.
          </p>
        ) : (
          <>
            <h2 className={styles.subheading}>Cart</h2>
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
            {currency === null ? (
              <p className={styles.error}>
                Cart lines use mixed currencies. Remove lines until one currency
                remains.
              </p>
            ) : null}

            <h2 className={styles.subheading}>Seller disclosure</h2>
            {loadError !== null ? (
              <p className={styles.error}>{loadError}</p>
            ) : disclosure === null ? (
              <p className={styles.meta}>Loading disclosure…</p>
            ) : !disclosure.complete ? (
              <>
                <p className={styles.error}>
                  Checkout is unavailable while seller disclosure is incomplete.
                </p>
                <p className={styles.meta}>Missing items:</p>
                <ul className={styles.list}>
                  {disclosure.missing.map((item) => (
                    <li key={item}>
                      <code>{item}</code>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <dl className={styles.disclosureList}>
                {DISCLOSURE_FIELDS.map(({ key, label }) => (
                  <div key={key} className={styles.disclosureRow}>
                    <dt>{label}</dt>
                    <dd>{formatField(key, disclosure.disclosure)}</dd>
                  </div>
                ))}
              </dl>
            )}

            <h2 className={styles.subheading}>Payment provider</h2>
            <fieldset className={styles.fieldset} disabled={!canPay && !paying}>
              <legend className={styles.legend}>Choose a provider</legend>
              {PROVIDERS.map((provider) => (
                <label key={provider.id} className={styles.radioLabel}>
                  <input
                    type="radio"
                    name="provider"
                    value={provider.id}
                    checked={providerId === provider.id}
                    disabled={!canPay && !paying}
                    onChange={() => setProviderId(provider.id)}
                  />
                  {provider.label}
                </label>
              ))}
            </fieldset>

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.button}
                disabled={!canPay}
                onClick={() => {
                  void onPay();
                }}
              >
                {paying ? "Redirecting…" : "Pay"}
              </button>
            </div>
            {payError !== null ? <p className={styles.error}>{payError}</p> : null}
            <p className={styles.status}>
              Buyer identity is the configured demo buyer id until account auth
              lands. <Link href="/cart">Back to cart</Link>
            </p>
          </>
        )}
      </main>
    </div>
  );
}
