"use client";

import { Button, type ButtonSize } from "@/components/ui/Button";
import { useCart } from "./CartProvider";

type Props = {
  candidateId: string;
  title: string;
  unitAmount: string;
  currency: string;
  /** The visible label, from the dictionary of the active locale. */
  label: string;
  /** Shown once the good is in the cart. */
  addedLabel: string;
  size?: ButtonSize;
  className?: string;
};

/**
 * Adds a good to the cart and confirms it on the button itself, without navigating away:
 * the buyer stays in the catalogue, and the header badge and the live region in
 * `CartProvider` report the change as well.
 *
 * The confirmation is read from the cart's membership rather than held as component state,
 * so every copy of this action for the same good — the buy box, the repeat below the detail
 * and the sticky bar — reads the same label after one of them is used. Three copies with
 * three independent `added` flags is what made them disagree (audit finding 14).
 *
 * Both labels share one grid cell so the button is as wide as the wider of the two and a
 * state change never moves the price beside it.
 */
export function AddToCartButton({
  candidateId,
  title,
  unitAmount,
  currency,
  label,
  addedLabel,
  size = "md",
  className,
}: Props) {
  const { add, lines } = useCart();
  const added = lines.some((line) => line.candidate_id === candidateId);

  function onClick(): void {
    add({
      candidate_id: candidateId,
      unit_amount: unitAmount,
      quantity: 1,
      currency,
      title,
    });
  }

  return (
    <Button
      size={size}
      className={className}
      variant={added ? "secondary" : "primary"}
      onClick={onClick}
    >
      <span className="grid">
        <span className="col-start-1 row-start-1" aria-hidden={added}>
          {label}
        </span>
        <span className="col-start-1 row-start-1" aria-hidden={!added}>
          {addedLabel}
        </span>
      </span>
    </Button>
  );
}
