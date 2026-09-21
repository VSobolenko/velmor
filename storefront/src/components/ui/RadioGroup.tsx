"use client";

/**
 * Wraps `@radix-ui/react-radio-group`. This file is the only place that package is
 * imported; the payment provider choice reaches a radio group through
 * `@/components/ui/RadioGroup`.
 *
 * A radio group is more than circles with a shared name: `role="radiogroup"` with its own
 * name, `role="radio"` with `aria-checked` on each item, arrow keys moving the selection
 * and a single tab stop (roving tabindex) rather than one per option. Each item here is
 * the whole labelled card, not a bare dot beside a separate label, so the target is the
 * card and the accessible name is the card's text. Radix owns that behaviour; this file
 * owns the token styling and the prop names.
 *
 * The group's accessible name comes from the `label` prop on the root, and each item's
 * from `aria-labelledby` on its own label element.
 */

import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";
import { useId } from "react";
import { classNames } from "./classes";

export type RadioOption = {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
};

type Props = {
  /** The group's accessible name. */
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  options: readonly RadioOption[];
  className?: string;
};

export function RadioGroup({
  label,
  value,
  onValueChange,
  options,
  className,
}: Props) {
  const groupId = useId();
  return (
    <RadioGroupPrimitive.Root
      aria-label={label}
      value={value}
      onValueChange={onValueChange}
      className={classNames("flex flex-col gap-2", className)}
    >
      {options.map((option, index) => {
        const itemId = `${groupId}-${index}`;
        const labelId = `${itemId}-label`;
        const descriptionId = `${itemId}-description`;
        return (
          <RadioGroupPrimitive.Item
            key={option.value}
            id={itemId}
            value={option.value}
            disabled={option.disabled ?? false}
            aria-labelledby={labelId}
            aria-describedby={
              option.description === undefined ? undefined : descriptionId
            }
            className={classNames(
              "tap-target flex w-full items-start gap-3 rounded-md border border-line-strong bg-surface p-3 text-left text-ink",
              "data-[state=checked]:border-accent-strong data-[state=checked]:bg-accent-soft",
              "disabled:cursor-not-allowed disabled:opacity-60",
            )}
          >
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-pill border border-line-strong">
              <RadioGroupPrimitive.Indicator className="h-2 w-2 rounded-pill bg-accent-strong" />
            </span>
            <span className="flex flex-col">
              <span id={labelId} className="text-sm font-medium">
                {option.label}
              </span>
              {option.description === undefined ? null : (
                <span id={descriptionId} className="text-sm text-muted">
                  {option.description}
                </span>
              )}
            </span>
          </RadioGroupPrimitive.Item>
        );
      })}
    </RadioGroupPrimitive.Root>
  );
}
