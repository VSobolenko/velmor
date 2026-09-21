"use client";

/**
 * Wraps `@radix-ui/react-select`. This file is the only place that package is imported;
 * sort and the language switcher reach an option list through
 * `@/components/ui/Combobox`.
 *
 * It is not a restyled `<select>`, and that is the reason it exists next to the plain
 * `Select` component: a native select can only carry a string per option, so an option
 * that needs a colour swatch or a count cannot be expressed at all. Radix also owns the
 * parts a hand-written listbox loses - `role="combobox"` with `aria-expanded` and
 * `aria-controls`, arrow-key roving focus with `aria-activedescendant`, typeahead,
 * Escape, and the hidden native select it renders for form submission. This file owns the
 * token styling and the prop names.
 *
 * The control's accessible name comes from the `label` prop, on both the visible `<label>`
 * and the trigger's `aria-label`, so the name exists whether or not the label is hidden.
 */

import * as SelectPrimitive from "@radix-ui/react-select";
import { useId } from "react";
import { classNames } from "./classes";

export type ComboboxOption = {
  value: string;
  /** The option's text: the trigger's value, the typeahead source and the listbox name. */
  label: string;
  /** Secondary text beside the label, for example a result count. */
  description?: string;
  /** A token background class for a colour chip, for example `bg-accent`. A raw hex value
   * is not accepted here: colours come from the token set. */
  swatchClassName?: string;
};

type Props = {
  /** The control's accessible name. */
  label: string;
  options: readonly ComboboxOption[];
  /** The selected value. The empty string means nothing is selected yet, and the trigger
   * then shows `placeholder`. */
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  /** Keeps the label for assistive technology but not for sighted users. */
  hideLabel?: boolean;
  /** The form field name of the hidden native select Radix renders. */
  name?: string;
  disabled?: boolean;
  className?: string;
};

const CHEVRON = (
  <svg
    aria-hidden="true"
    viewBox="0 0 12 12"
    className="h-3 w-3 stroke-current"
  >
    <path d="M2 4.5 6 8.5 10 4.5" fill="none" strokeWidth="1.5" />
  </svg>
);

const CHECK = (
  <svg
    aria-hidden="true"
    viewBox="0 0 12 12"
    className="h-3 w-3 stroke-current"
  >
    <path d="M2 6.5 4.5 9 10 3.5" fill="none" strokeWidth="1.5" />
  </svg>
);

export function Combobox({
  label,
  options,
  value,
  onValueChange,
  placeholder,
  hideLabel = false,
  name,
  disabled = false,
  className,
}: Props) {
  const triggerId = useId();
  return (
    <div className="flex w-full flex-col gap-1">
      <label
        htmlFor={triggerId}
        className={hideLabel ? "sr-only" : "text-sm font-medium text-ink"}
      >
        {label}
      </label>
      <SelectPrimitive.Root
        value={value}
        onValueChange={onValueChange}
        name={name}
        disabled={disabled}
      >
        <SelectPrimitive.Trigger
          id={triggerId}
          aria-label={label}
          className={classNames(
            "tap-target flex w-full items-center justify-between gap-2 rounded-md border border-line-strong bg-surface px-3 py-2 text-left text-ink",
            className,
          )}
        >
          <SelectPrimitive.Value placeholder={placeholder} />
          <SelectPrimitive.Icon>{CHEVRON}</SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            position="popper"
            sideOffset={4}
            className="z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-line bg-surface shadow-md"
          >
            <SelectPrimitive.Viewport className="p-1">
              {options.map((option) => (
                <SelectPrimitive.Item
                  key={option.value}
                  value={option.value}
                  textValue={option.label}
                  className="tap-target flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-ink data-[highlighted]:bg-surface-sunken"
                >
                  <SelectPrimitive.ItemIndicator className="text-accent-strong">
                    {CHECK}
                  </SelectPrimitive.ItemIndicator>
                  {option.swatchClassName === undefined ? null : (
                    <span
                      aria-hidden="true"
                      className={classNames(
                        "h-4 w-4 shrink-0 rounded-sm border border-line-strong",
                        option.swatchClassName,
                      )}
                    />
                  )}
                  <SelectPrimitive.ItemText>
                    {option.label}
                  </SelectPrimitive.ItemText>
                  {option.description === undefined ? null : (
                    <span className="text-sm text-muted">
                      {option.description}
                    </span>
                  )}
                </SelectPrimitive.Item>
              ))}
            </SelectPrimitive.Viewport>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>
    </div>
  );
}
