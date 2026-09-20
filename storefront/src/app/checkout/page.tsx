"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PaymentMarks } from "@/components/PaymentMarks";
import { ShopChrome } from "@/components/ShopChrome";
import {
  CommerceApiClient,
  CommerceApiError,
  type CheckoutDisclosureResponse,
} from "@/lib/api";
import { type CartLine, readCart } from "@/lib/cart";
import { copy } from "@/lib/copy";
import styles from "../shop.module.css";

const ORDER_STORAGE_KEY = "velmor.checkout.order_id";

type ProviderId = "stripe" | "bepaid";

const PROVIDERS: { id: ProviderId; label: string }[] = [
  { id: "stripe", label: copy.providerStripe },
  { id: "bepaid", label: copy.providerBepaid },
];

const DISCLOSURE_FIELDS: {
  key: keyof CheckoutDisclosureResponse["disclosure"];
  label: string;
}[] = [
  { key: "legal_name", label: copy.disclosureLegalName },
  { key: "registration_number", label: copy.disclosureRegNumber },
  { key: "registration_date", label: copy.disclosureRegDate },
  { key: "registration_authority", label: copy.disclosureRegAuthority },
  { key: "shop_register_number", label: copy.disclosureShopRegister },
  { key: "postal_address", label: copy.disclosurePostal },
  { key: "working_hours", label: copy.disclosureHours },
  { key: "contact_details", label: copy.disclosureContact },
  { key: "payment_rules", label: copy.disclosurePaymentRules },
  { key: "return_rules", label: copy.disclosureReturnRules },
  { key: "payment_system_marks", label: copy.disclosurePaymentMarks },
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
              : copy.disclosureLoadFailed;
        setLoadError(detail);
      });
  }, []);

  async function onPay() {
    setPayError(null);
    const currency = cartCurrency(lines);
    if (currency === null) {
      setPayError(copy.cartMustShareCurrency);
      return;
    }
    if (disclosure === null || !disclosure.complete) {
      setPayError(copy.checkoutUnavailableDisclosure);
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
            : copy.checkoutFailed;
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
    <ShopChrome tagline={copy.checkout}>
      <main className={styles.main}>
        <h1 className={styles.heading}>{copy.checkout}</h1>
        {!clientReady ? (
          <p className={styles.meta}>{copy.loading}</p>
        ) : lines.length === 0 ? (
          <p className={styles.empty}>
            {copy.cartEmptyCheckout}{" "}
            <Link href="/">{copy.browseCatalogue}</Link>.
          </p>
        ) : (
          <>
            <h2 className={styles.subheading}>{copy.cart}</h2>
            <ul className={styles.list}>
              {lines.map((line) => (
                <li key={line.candidate_id} className={styles.cartLine}>
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
              <p className={styles.error}>{copy.mixedCurrency}</p>
            ) : null}

            <h2 className={styles.subheading}>{copy.sellerDisclosure}</h2>
            {loadError !== null ? (
              <p className={styles.error}>{loadError}</p>
            ) : disclosure === null ? (
              <p className={styles.meta}>{copy.disclosureLoading}</p>
            ) : !disclosure.complete ? (
              <>
                <p className={styles.error}>{copy.disclosureIncomplete}</p>
                <p className={styles.meta}>{copy.missingItems}</p>
                <ul className={styles.list}>
                  {disclosure.missing.map((item) => (
                    <li key={item}>
                      <code>{item}</code>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <>
                <dl className={styles.disclosureList}>
                  {DISCLOSURE_FIELDS.filter(
                    ({ key }) => key !== "payment_system_marks",
                  ).map(({ key, label }) => (
                    <div key={key} className={styles.disclosureRow}>
                      <dt>{label}</dt>
                      <dd>{formatField(key, disclosure.disclosure)}</dd>
                    </div>
                  ))}
                </dl>
                <div className={styles.checkoutMarks}>
                  <PaymentMarks
                    marks={disclosure.disclosure.payment_system_marks}
                    labelled
                  />
                </div>
              </>
            )}

            <h2 className={styles.subheading}>{copy.paymentProvider}</h2>
            <fieldset className={styles.fieldset} disabled={!canPay && !paying}>
              <legend className={styles.legend}>{copy.chooseProvider}</legend>
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
                {paying ? copy.redirecting : copy.pay}
              </button>
            </div>
            {payError !== null ? <p className={styles.error}>{payError}</p> : null}
            <p className={styles.status}>
              {copy.buyerDemoNote}{" "}
              <Link href="/cart">{copy.backToCart}</Link>
            </p>
          </>
        )}
      </main>
    </ShopChrome>
  );
}
