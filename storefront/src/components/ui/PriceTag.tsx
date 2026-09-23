import { classNames } from "./classes";

type Props = {
  /** A decimal amount exactly as the API sends it: `"9.99"`. Never reformatted here. */
  amount: string;
  /** An ISO code: `"USD"`. */
  currency: string;
  size?: "md" | "lg";
};

/**
 * The amount is the display face at weight 600 and the currency is the same face, lighter and
 * muted: that difference is what makes the pair read as a price rather than as two strings.
 */
export function PriceTag({ amount, currency, size = "md" }: Props) {
  return (
    <span
      className={classNames(
        "inline-flex items-baseline gap-1 font-heading font-semibold text-ink",
        size === "lg" ? "text-3xl" : "text-lg",
      )}
    >
      <span>{amount}</span>
      <span
        className={classNames(
          "font-normal text-muted",
          size === "lg" ? "text-base" : "text-sm",
        )}
      >
        {currency}
      </span>
    </span>
  );
}
