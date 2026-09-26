"use client";

import Link from "next/link";
import { useCart } from "@/components/CartProvider";
import { PreviewImage } from "@/components/PreviewImage";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PriceTag } from "@/components/ui/PriceTag";
import { cartTotal } from "@/lib/cart";
import { useCartTitles } from "@/lib/cart-titles";
import { dictionaryFor } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";
import { useLocale } from "@/lib/i18n/use-locale";
import { previewSrc } from "@/lib/media";

/**
 * The cart: a preview and a quantity stepper per line, a summary that states the total and its
 * currency, and one checkout action. A mixed-currency cart has no honest total, so the summary
 * says so and the checkout action is not offered.
 *
 * The stepper is a labelled group of two buttons around the value: a number input's own
 * spinners are far below the 44 px target and are hover-only on a desktop.
 */
export default function CartPage() {
  const locale = useLocale();
  const dict = dictionaryFor(locale);
  const { lines, total, remove, setQuantity } = useCart();
  const { lines: displayLines } = useCartTitles(lines, locale);
  const catalogueHref = localePath(locale, "/catalogue");

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-gutter-lg px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["cart.title"]}
      </h1>

      {lines.length === 0 ? (
        <EmptyState
          title={dict["cart.empty"]}
          action={
            <Link className={buttonClassName("primary")} href={catalogueHref}>
              {dict["cart.emptyCta"]}
            </Link>
          }
        />
      ) : (
        <div className="grid items-start gap-gutter-lg lg:grid-cols-[minmax(0,1fr)_20rem]">
          <Card padding="none">
            <ul className="divide-y divide-line">
              {displayLines.map((line) => {
                const subtotal = cartTotal([line]);
                return (
                  <li
                    key={line.candidate_id}
                    className="flex gap-3 p-4 sm:gap-4"
                  >
                    <div className="h-20 w-20 shrink-0 overflow-hidden rounded-md bg-surface-sunken sm:h-24 sm:w-24">
                      <PreviewImage
                        src={previewSrc(line.candidate_id)}
                        alt={line.title}
                      />
                    </div>
                    <div className="flex min-w-0 flex-1 flex-col gap-2">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <Link
                          className="tap-target inline-flex min-w-0 flex-1 items-center font-heading text-base font-semibold leading-snug text-ink hover:underline"
                          href={localePath(
                            locale,
                            `/goods/${encodeURIComponent(line.candidate_id)}`,
                          )}
                        >
                          {line.title}
                        </Link>
                        {subtotal === null ? null : (
                          <span className="flex items-baseline gap-2 text-sm text-muted">
                            <span>{dict["cart.subtotal"]}</span>
                            <PriceTag
                              amount={subtotal.amount}
                              currency={subtotal.currency}
                            />
                          </span>
                        )}
                      </div>
                      <p className="flex flex-wrap items-baseline gap-2 text-sm text-muted">
                        <PriceTag
                          amount={line.unit_amount}
                          currency={line.currency}
                        />
                        <span>{dict["cart.each"]}</span>
                      </p>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div
                          role="group"
                          aria-label={`${dict["cart.quantity"]}: ${line.title}`}
                          className="flex items-center gap-2"
                        >
                          <Button
                            variant="secondary"
                            size="sm"
                            aria-label={`${dict["cart.quantity"]} −`}
                            disabled={line.quantity <= 1}
                            onClick={() =>
                              setQuantity(line.candidate_id, line.quantity - 1)
                            }
                          >
                            −
                          </Button>
                          <span className="min-w-8 text-center text-base tabular-nums text-ink">
                            {line.quantity}
                          </span>
                          <Button
                            variant="secondary"
                            size="sm"
                            aria-label={`${dict["cart.quantity"]} +`}
                            onClick={() =>
                              setQuantity(line.candidate_id, line.quantity + 1)
                            }
                          >
                            +
                          </Button>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => remove(line.candidate_id)}
                        >
                          {dict["cart.remove"]}
                        </Button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>

          <aside>
            <Card className="flex flex-col gap-4">
              {total === null ? (
                <p className="text-sm text-danger">
                  {dict["cart.currencyMismatch"]}
                </p>
              ) : (
                <>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-sm text-muted">
                      {dict["cart.total"]}
                    </span>
                    <PriceTag
                      amount={total.amount}
                      currency={total.currency}
                      size="lg"
                    />
                  </div>
                  <Link
                    className={buttonClassName("primary", "lg", "w-full")}
                    href={localePath(locale, "/checkout")}
                  >
                    {dict["cart.checkout"]}
                  </Link>
                </>
              )}
              <Link
                className={buttonClassName("secondary", "md", "w-full")}
                href={catalogueHref}
              >
                {dict["cart.continueShopping"]}
              </Link>
            </Card>
          </aside>
        </div>
      )}
    </main>
  );
}
