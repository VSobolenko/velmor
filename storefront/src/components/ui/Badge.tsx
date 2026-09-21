import type { ReactNode } from "react";
import { classNames } from "./classes";

/*
 * `neutral`, `accent` and `danger` are the general tones. `success` and `warning` are the
 * order-state pair — a paid order reads as an ink stamp, an unpaid one as a light outlined
 * plate — so a state is legible next to a licence badge without a second accent colour.
 */
export type BadgeTone =
  | "neutral"
  | "accent"
  | "success"
  | "warning"
  | "danger";

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: "bg-surface-sunken text-ink",
  accent: "bg-accent-soft text-accent-strong",
  success: "bg-surface-inverse text-ink-inverse",
  warning: "border border-line-strong bg-surface text-ink",
  danger: "border border-danger text-danger",
};

type Props = {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
};

/**
 * The badge adds no icon of its own: it names a state and lets the type carry it. The square
 * corner and the small type scale keep it reading as a stamped mark rather than a pill.
 */
export function Badge({ tone = "neutral", className, children }: Props) {
  return (
    <span
      className={classNames(
        "inline-flex items-center gap-1 rounded-sm px-2.5 py-1 text-xs font-medium tracking-wide",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
