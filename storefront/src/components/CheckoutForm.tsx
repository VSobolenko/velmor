"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { SignInRequired } from "@/components/AccountGateActions";
import { useCart } from "@/components/CartProvider";
import { PaymentMarks } from "@/components/PaymentMarks";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PriceTag } from "@/components/ui/PriceTag";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  CommerceApiClient,
  type CheckoutDisclosureResponse,
  type SellerDisclosurePayload,
} from "@/lib/api";
import { type CartLine } from "@/lib/cart";
import { useCartTitles } from "@/lib/cart-titles";
import { dictionaryFor, type Dictionary } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";
import { useLocale } from "@/lib/i18n/use-locale";

/** Where the checkout page leaves the order id for the return page when the provider omits it. */
const ORDER_STORAGE_KEY = "velmor.checkout.order_id";

const PROVIDER_LABEL_KEYS: Record<string, keyof Dictionary> = {
  stripe: "checkout.providerStripe",
  bepaid: "checkout.providerBepaid",
  stub: "checkout.providerStub",
};

type DisclosureFieldKey = Exclude<
  keyof SellerDisclosurePayload,
  "payment_system_marks"
>;

const DISCLOSURE_FIELDS: {
  key: DisclosureFieldKey;
  labelKey: keyof Dictionary;
}[] = [
  { key: "legal_name", labelKey: "checkout.disclosureLegalName" },
  { key: "registration_number", labelKey: "checkout.disclosureRegNumber" },
  { key: "registration_date", labelKey: "checkout.disclosureRegDate" },
  {
    key: "registration_authority",
    labelKey: "checkout.disclosureRegAuthority",
  },
  { key: "shop_register_number", labelKey: "checkout.disclosureShopRegister" },
  { key: "postal_address", labelKey: "checkout.disclosurePostal" },
  { key: "working_hours", labelKey: "checkout.disclosureHours" },
  { key: "contact_details", labelKey: "checkout.disclosureContact" },
  { key: "payment_rules", labelKey: "checkout.disclosurePaymentRules" },
  { key: "return_rules", labelKey: "checkout.disclosureReturnRules" },
];

/** The name the API reported as missing as the buyer's label, or the raw name if it is unknown. */
function missingLabel(name: string, dict: Dictionary): string {
  const field = DISCLOSURE_FIELDS.find((entry) => entry.key === name);
  return field === undefined ? name : dict[field.labelKey];
}

function providerLabel(id: string, dict: Dictionary): string {
  const labelKey = PROVIDER_LABEL_KEYS[id];
  return labelKey === undefined ? id : dict[labelKey];
}

/** The one currency a cart may be paid in; `null` when it is empty or holds more than one. */
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

type CheckoutFormProps = {
  /**
   * Whether the caller has a session, resolved on the server by `accountGate`'s read of
   * `/auth/me`. Checkout needs an identifiable buyer, so with no session the payment controls
   * are not rendered at all and the buyer is shown how to sign in; the cart, the seller
   * disclosure and the way back to the cart stay readable.
   */
  signedIn: boolean;
};

export function CheckoutForm({ signedIn }: CheckoutFormProps) {
  const locale = useLocale();
  const dict = dictionaryFor(locale);
  const { lines, total } = useCart();
  const { lines: displayLines, loading: titlesLoading } = useCartTitles(lines, locale);
  const [disclosure, setDisclosure] =
    useState<CheckoutDisclosureResponse | null>(null);
  const [disclosureFailed, setDisclosureFailed] = useState(false);
  /* Bumped by the retry control to re-run the disclosure fetch without a page reload. */
  const [disclosureAttempt, setDisclosureAttempt] = useState(0);
  const [providers, setProviders] = useState<string[] | null>(null);
  const [providersFailed, setProvidersFailed] = useState(false);
  const [providerId, setProviderId] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [acknowledgementMissing, setAcknowledgementMissing] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  /*
   * The in-flight guard. A ref, not the `paying` state: `onPay` runs from the wrapping div's
   * click handler and two clicks can arrive before React has committed the `setPaying(true)`
   * render, so a state check would let the second click through and post a second order. The
   * ref is written synchronously before the request starts.
   */
  const payingRef = useRef(false);

  const cartIsEmpty = lines.length === 0;

  useEffect(() => {
    // Loaded even for an empty cart: the footer's seller-disclosure link points at this page's
    // `#disclosure`, and the seller's legal identity must be readable in exactly the state
    // that prompts the click.
    let cancelled = false;
    const client = CommerceApiClient.fromEnv(locale);
    client
      .getCheckoutDisclosure()
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setDisclosure(payload);
        setDisclosureFailed(false);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setDisclosure(null);
        setDisclosureFailed(true);
      });
    client
      .listCheckoutProviders()
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setProviders(payload);
        setProvidersFailed(false);
        setProviderId(payload[0] ?? null);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setProviders(null);
        setProvidersFailed(true);
        setProviderId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [locale, disclosureAttempt]);

  const currency = cartCurrency(lines);
  const disclosureReady = disclosure !== null && disclosure.complete;
  const paymentBlocked =
    cartIsEmpty ||
    titlesLoading ||
    paying ||
    !accepted ||
    disclosureReady === false ||
    currency === null ||
    providerId === null;

  async function startCheckout(payCurrency: string, provider: string): Promise<void> {
    const client = CommerceApiClient.fromEnv(locale);
    const returnUrl = new URL(
      localePath(locale, "/checkout/return"),
      window.location.origin,
    ).toString();
    // The guard is set synchronously, before the first await: a second click reaching `onPay`
    // while this request is in flight returns there and never posts a second order.
    payingRef.current = true;
    setPaying(true);
    try {
      const started = await client.startCheckout({
        provider_id: provider,
        return_url: returnUrl,
        currency: payCurrency,
        lines: displayLines.map((line) => ({
          candidate_id: line.candidate_id,
          unit_amount: line.unit_amount,
          quantity: line.quantity,
        })),
      });
      window.sessionStorage.setItem(ORDER_STORAGE_KEY, started.order_id);
      window.location.assign(started.redirect_url);
    } catch {
      setPayError(dict["checkout.checkoutFailed"]);
      // A failed request releases the guard, so the buyer can correct the cause and pay again.
      payingRef.current = false;
      setPaying(false);
    }
  }

  /**
   * The one validation path. It is reachable while the pay button is disabled: the button drops
   * pointer events when it is blocked, so the wrapping div receives the click and the buyer is
   * told which requirement is missing instead of facing a dead control.
   */
  function onPay(): void {
    // A request is already in flight: the buyer's second click changes nothing and must not
    // reach the checks below, which would run `startCheckout` again.
    if (payingRef.current) {
      return;
    }
    setPayError(null);
    const payCurrency = cartCurrency(lines);
    if (payCurrency === null) {
      setPayError(dict["checkout.mustShareCurrency"]);
      return;
    }
    if (disclosure === null || !disclosure.complete) {
      setPayError(dict["checkout.unavailableDisclosure"]);
      return;
    }
    if (!accepted) {
      setAcknowledgementMissing(true);
      return;
    }
    if (providerId === null) {
      return;
    }
    void startCheckout(payCurrency, providerId);
  }

  /*
   * One element, rendered in both the empty and the filled cart: the footer's
   * `/checkout#disclosure` link must reach the seller's legal identity in the empty state too,
   * which is exactly the state that prompts a buyer to look for it.
   */
  const disclosureSection = (
    <section id="disclosure" className="flex flex-col gap-3">
      <h2 className="font-heading text-lg font-semibold text-ink">
        {dict["checkout.disclosureTitle"]}
      </h2>
      {disclosureFailed ? (
        <ErrorState
          title={dict["checkout.disclosureLoadFailed"]}
          description={dict["common.errorBody"]}
          action={
            <Button
              variant="secondary"
              size="md"
              onClick={() => {
                setDisclosure(null);
                setDisclosureFailed(false);
                setDisclosureAttempt((attempt) => attempt + 1);
              }}
            >
              {dict["common.retry"]}
            </Button>
          }
        />
      ) : disclosure === null ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">
            {dict["checkout.disclosureLoading"]}
          </p>
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-4/5" />
          <Skeleton className="h-5 w-2/3" />
        </div>
      ) : !disclosure.complete ? (
        <div className="flex flex-col gap-2">
          <p role="alert" className="text-sm text-danger">
            {dict["checkout.disclosureIncomplete"]}
          </p>
          <p className="text-sm text-muted">
            {dict["checkout.disclosureMissing"]}
          </p>
          <ul className="list-disc pl-5 text-sm text-muted">
            {disclosure.missing.map((name) => (
              <li key={name}>{missingLabel(name, dict)}</li>
            ))}
          </ul>
        </div>
      ) : (
        <Card className="flex flex-col gap-4">
          <dl className="flex flex-col gap-2">
            {DISCLOSURE_FIELDS.map((field) => {
              const value = disclosure.disclosure[field.key];
              return (
                <div
                  key={field.key}
                  className="flex flex-col gap-0.5 sm:flex-row sm:gap-3"
                >
                  <dt className="text-sm text-muted sm:w-56 sm:shrink-0">
                    {dict[field.labelKey]}
                  </dt>
                  <dd className="text-sm text-ink">
                    {value === null ? "\u2014" : value}
                  </dd>
                </div>
              );
            })}
          </dl>
          <PaymentMarks
            marks={disclosure.disclosure.payment_system_marks}
            label={dict["checkout.disclosurePaymentMarks"]}
          />
        </Card>
      )}
    </section>
  );

  if (cartIsEmpty) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-gutter-lg px-gutter py-section">
        <h1 className="font-heading text-2xl font-semibold text-ink">
          {dict["checkout.title"]}
        </h1>
        <EmptyState
          title={dict["checkout.empty"]}
          action={
            <Link
              className={buttonClassName("primary")}
              href={localePath(locale, "/catalogue")}
            >
              {dict["checkout.emptyCta"]}
            </Link>
          }
        />
        {disclosureSection}
      </main>
    );
  }

  const steps = [
    { label: dict["checkout.stepCart"], current: false },
    { label: dict["checkout.stepDetails"], current: false },
    { label: dict["checkout.stepPayment"], current: true },
  ];

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-gutter-lg px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["checkout.title"]}
      </h1>

      <nav aria-label={dict["checkout.stepsLabel"]}>
        <ol className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          {steps.map((step, index) => (
            <li
              key={step.label}
              aria-current={step.current ? "step" : undefined}
              className="flex items-center gap-2"
            >
              <span
                aria-hidden="true"
                className={
                  step.current
                    ? "flex h-6 w-6 items-center justify-center rounded-pill bg-accent text-xs font-semibold text-ink-inverse"
                    : "flex h-6 w-6 items-center justify-center rounded-pill bg-surface-sunken text-xs font-semibold text-muted"
                }
              >
                {index + 1}
              </span>
              <span className={step.current ? "font-medium text-ink" : "text-muted"}>
                {step.label}
              </span>
            </li>
          ))}
        </ol>
      </nav>

      <section className="flex flex-col gap-3">
        <h2 className="font-heading text-lg font-semibold text-ink">
          {dict["checkout.summary"]}
        </h2>
        <Card padding="sm">
          <ul className="divide-y divide-line">
            {displayLines.map((line) => (
              <li
                key={line.candidate_id}
                className="flex flex-wrap items-baseline justify-between gap-2 py-2"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-ink">
                  {line.title}
                </span>
                <span className="flex items-baseline gap-2">
                  <PriceTag
                    amount={line.unit_amount}
                    currency={line.currency}
                  />
                  <span className="text-sm text-muted">{`\u00d7 ${line.quantity}`}</span>
                </span>
              </li>
            ))}
          </ul>
          {total === null ? (
            <p className="pt-2 text-sm text-danger">
              {dict["checkout.mixedCurrency"]}
            </p>
          ) : (
            <div className="flex items-baseline justify-between gap-3 border-t border-line pt-3">
              <span className="text-sm text-muted">{dict["cart.total"]}</span>
              <PriceTag
                amount={total.amount}
                currency={total.currency}
                size="lg"
              />
            </div>
          )}
        </Card>
      </section>

      {disclosureSection}

      {signedIn ? (
        <>
          <section className="flex flex-col gap-3">
            <h2 className="font-heading text-lg font-semibold text-ink">
              {dict["checkout.provider"]}
            </h2>
            <fieldset className="flex flex-col gap-3">
              <legend className="text-sm text-muted">
                {dict["checkout.chooseProvider"]}
              </legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {providersFailed ? (
                  <ErrorState
                    title={dict["common.errorTitle"]}
                    description={dict["common.errorBody"]}
                  />
                ) : providers === null ? (
                  <Skeleton className="h-16 w-full" />
                ) : (
                  providers.map((id) => (
                    <label key={id} className="cursor-pointer">
                      <input
                        type="radio"
                        name="provider"
                        value={id}
                        checked={providerId === id}
                        onChange={() => setProviderId(id)}
                        className="peer sr-only"
                      />
                      <span className="tap-target flex items-center gap-3 rounded-lg border border-line bg-surface p-4 text-ink transition-colors duration-base ease-standard hover:border-line-strong peer-checked:border-accent peer-checked:bg-accent-soft peer-checked:text-accent-strong peer-focus-visible:ring-2 peer-focus-visible:ring-accent-strong">
                        <span
                          aria-hidden="true"
                          className={
                            providerId === id
                              ? "h-4 w-4 shrink-0 rounded-pill border-4 border-accent"
                              : "h-4 w-4 shrink-0 rounded-pill border border-line-strong"
                          }
                        />
                        <span className="font-medium">{providerLabel(id, dict)}</span>
                      </span>
                    </label>
                  ))
                )}
              </div>
            </fieldset>
          </section>

          <Card className="flex flex-col gap-3">
            <Checkbox
              label={dict["checkout.licenceAck"]}
              checked={accepted}
              onCheckedChange={(checked) => {
                setAccepted(checked === true);
                if (checked === true) {
                  setAcknowledgementMissing(false);
                }
              }}
            />
            {acknowledgementMissing ? (
              <p role="alert" className="text-sm text-danger">
                {dict["checkout.licenceAckRequired"]}
              </p>
            ) : null}
          </Card>

          <div className="flex flex-col gap-3" onClick={onPay}>
            <Button
              className={paymentBlocked ? "pointer-events-none w-full" : "w-full"}
              size="lg"
              disabled={paymentBlocked}
              loading={paying}
              loadingLabel={dict["checkout.redirecting"]}
            >
              {dict["checkout.pay"]}
            </Button>
          </div>
          {payError !== null ? (
            <p role="alert" className="text-sm text-danger">
              {payError}
            </p>
          ) : null}
        </>
      ) : (
        <SignInRequired
          locale={locale}
          title={dict["checkout.signInRequired"]}
          actionLabel={dict["checkout.signInCta"]}
          headingLevel={2}
        />
      )}

      <Link
        className="tap-target inline-flex w-fit items-center text-sm font-medium text-accent-strong hover:underline"
        href={localePath(locale, "/cart")}
      >
        {dict["checkout.backToCart"]}
      </Link>
    </main>
  );
}
