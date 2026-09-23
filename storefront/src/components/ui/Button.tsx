import type { ButtonHTMLAttributes, ReactNode } from "react";
import { classNames } from "./classes";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

/*
 * One filled accent button per view is the rule; every other action is `secondary` or
 * `ghost`. `danger` is a separate semantic, not a second accent, and it has no dedicated
 * darker token: the accent-strong value is its neighbour in the same warm-red family and
 * is the only token that darkens it.
 */
const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-accent text-ink-inverse hover:bg-accent-strong",
  secondary:
    "border border-line-strong bg-surface text-ink hover:bg-surface-sunken",
  ghost: "bg-transparent text-ink hover:bg-surface-sunken",
  danger: "bg-danger text-ink-inverse hover:bg-accent-strong",
};

/*
 * The medium steps are the named rhythm values, so a button lines up with the gutters a
 * page shell uses. Radii stay at the small end: these are controls, not plates.
 */
const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-gutter py-2 text-base",
  lg: "px-gutter-lg py-3 text-lg",
};

/**
 * The button class set, for a `Link` that has to look like one. Every class here carries a
 * 44 px minimum target and a focus ring that is never removed.
 *
 * A disabled button keeps the same box and loses salience through opacity, the shadow and the
 * cursor, so it is perceivable as disabled even when the hues are indistinguishable.
 */
export function buttonClassName(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  extra?: string,
): string {
  return classNames(
    "tap-target inline-flex items-center justify-center gap-2 rounded-sm font-medium transition-colors duration-fast ease-standard disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none",
    VARIANT_CLASSES[variant],
    SIZE_CLASSES[size],
    extra,
  );
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  /** Shown in place of the label while loading; the button keeps the wider of the two. */
  loadingLabel?: string;
  children: ReactNode;
};

/**
 * The label and the loading label share one grid cell, so a state change never moves the
 * layout around the button.
 */
export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  loadingLabel,
  className,
  children,
  disabled = false,
  type = "button",
  ...rest
}: Props) {
  const busyLabel = loading ? loadingLabel : undefined;
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading}
      className={buttonClassName(variant, size, className)}
    >
      <span className="grid">
        <span
          className={`col-start-1 row-start-1${busyLabel !== undefined ? " invisible" : ""}`}
          aria-hidden={busyLabel !== undefined}
        >
          {children}
        </span>
        {busyLabel === undefined ? null : (
          <span className="col-start-1 row-start-1">{busyLabel}</span>
        )}
      </span>
    </button>
  );
}
