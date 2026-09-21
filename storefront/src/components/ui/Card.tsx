import type { HTMLAttributes, ReactNode } from "react";
import { classNames } from "./classes";

export type CardPadding = "none" | "sm" | "md";
export type CardVariant = "raised" | "flat";

const PADDING_CLASSES: Record<CardPadding, string> = {
  none: "",
  sm: "p-3",
  md: "p-5",
};

/*
 * Two cases only: a raised plate on paper, and a flat plate inside a grid where the
 * neighbour already separates it. Both share the hairline edge; only the raised one lifts.
 */
const VARIANT_CLASSES: Record<CardVariant, string> = {
  raised: "border border-line bg-surface shadow-sm",
  flat: "border border-line bg-surface",
};

type Props = HTMLAttributes<HTMLDivElement> & {
  padding?: CardPadding;
  variant?: CardVariant;
  children: ReactNode;
};

export function Card({
  padding = "md",
  variant = "raised",
  className,
  children,
  ...rest
}: Props) {
  return (
    <div
      {...rest}
      className={classNames(
        "rounded-lg",
        VARIANT_CLASSES[variant],
        PADDING_CLASSES[padding],
        className,
      )}
    >
      {children}
    </div>
  );
}
