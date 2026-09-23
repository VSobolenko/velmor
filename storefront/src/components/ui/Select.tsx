"use client";

import { useId } from "react";
import type { SelectHTMLAttributes } from "react";
import { classNames } from "./classes";

export type SelectOption = {
  value: string;
  label: string;
};

type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, "id" | "children"> & {
  label: string;
  options: readonly SelectOption[];
  /** Keeps the label for assistive technology but not for sighted users. */
  hideLabel?: boolean;
  /** A validation message. Present means invalid, and the control is described by it. */
  error?: string;
  /** Lets an inline control size itself to its contents instead of filling its container. */
  fullWidth?: boolean;
};

export function Select({
  label,
  options,
  hideLabel = false,
  error,
  fullWidth = true,
  className,
  ...rest
}: Props) {
  const id = useId();
  const errorId = `${id}-error`;
  const invalid = error !== undefined;
  return (
    <div className={classNames("flex flex-col gap-1", fullWidth ? "w-full" : "w-auto")}>
      <label
        htmlFor={id}
        className={hideLabel ? "sr-only" : "text-sm font-medium text-ink"}
      >
        {label}
      </label>
      <select
        {...rest}
        id={id}
        aria-invalid={invalid}
        aria-describedby={invalid ? errorId : undefined}
        className={classNames(
          "tap-target w-full rounded-sm border bg-surface px-3 py-2 text-ink transition-colors duration-fast ease-standard",
          invalid ? "border-danger" : "border-line-strong",
          className,
        )}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {invalid ? (
        <p id={errorId} role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
