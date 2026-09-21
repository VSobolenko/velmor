"use client";

/**
 * Wraps `@radix-ui/react-checkbox`. This file is the only place that package is imported;
 * the catalogue facets reach a checkbox through `@/components/ui/Checkbox`.
 *
 * A styled `<input type="checkbox">` cannot express the third state a facet needs - "some
 * of the goods in this category match" is neither checked nor unchecked - and hand-rolling
 * the third state loses `aria-checked="mixed"`, which is the only thing that tells a
 * screen reader the state at all. Radix owns the mixed state, the group-free roving focus
 * and the hidden native input it renders for a real form. This file owns the token styling
 * and the prop names.
 *
 * The accessible name comes from the `label` prop, on both the `<label>` and the root's
 * `aria-labelledby`, so the name does not depend on which association the browser honours.
 */

import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { useId } from "react";
import { classNames } from "./classes";

/** `"indeterminate"` is the mixed state a facet uses while only part of the set matches. */
export type CheckboxState = boolean | "indeterminate";

type Props = {
  /** The control's accessible name, and the text a buyer clicks. */
  label: string;
  checked: CheckboxState;
  onCheckedChange: (checked: CheckboxState) => void;
  /** Optional supporting line under the label. */
  description?: string;
  disabled?: boolean;
  /** The form field name of the hidden native input Radix renders. */
  name?: string;
  value?: string;
  className?: string;
};

export function Checkbox({
  label,
  checked,
  onCheckedChange,
  description,
  disabled = false,
  name,
  value,
  className,
}: Props) {
  const rootId = useId();
  const labelId = useId();
  return (
    <div className={classNames("flex items-start gap-2", className)}>
      <CheckboxPrimitive.Root
        id={rootId}
        aria-labelledby={labelId}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        name={name}
        value={value}
        className="tap-target flex shrink-0 items-center justify-center rounded-sm"
      >
        <span className="flex h-5 w-5 items-center justify-center rounded-sm border border-line-strong bg-surface">
          <CheckboxPrimitive.Indicator className="text-accent-strong">
            {checked === "indeterminate" ? (
              <svg
                aria-hidden="true"
                viewBox="0 0 12 12"
                className="h-3 w-3 stroke-current"
              >
                <path d="M3 6 H9" fill="none" strokeWidth="1.5" />
              </svg>
            ) : (
              <svg
                aria-hidden="true"
                viewBox="0 0 12 12"
                className="h-3 w-3 stroke-current"
              >
                <path d="M2 6.5 4.5 9 10 3.5" fill="none" strokeWidth="1.5" />
              </svg>
            )}
          </CheckboxPrimitive.Indicator>
        </span>
      </CheckboxPrimitive.Root>
      <div className="flex flex-col">
        <label
          id={labelId}
          htmlFor={rootId}
          className={classNames(
            "tap-target flex items-center text-sm text-ink",
            disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
          )}
        >
          {label}
        </label>
        {description === undefined ? null : (
          <p className="text-sm text-muted">{description}</p>
        )}
      </div>
    </div>
  );
}
