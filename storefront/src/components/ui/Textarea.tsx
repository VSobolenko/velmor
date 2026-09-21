"use client";

import { useId } from "react";
import type { TextareaHTMLAttributes } from "react";
import { classNames } from "./classes";

type Props = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> & {
  label: string;
  /** Keeps the label for assistive technology but not for sighted users. */
  hideLabel?: boolean;
  /** A validation message. Present means invalid, and the control is described by it. */
  error?: string;
};

export function Textarea({
  label,
  hideLabel = false,
  error,
  className,
  rows = 4,
  ...rest
}: Props) {
  const id = useId();
  const errorId = `${id}-error`;
  const invalid = error !== undefined;
  return (
    <div className="flex w-full flex-col gap-1">
      <label
        htmlFor={id}
        className={hideLabel ? "sr-only" : "text-sm font-medium text-ink"}
      >
        {label}
      </label>
      <textarea
        {...rest}
        id={id}
        rows={rows}
        aria-invalid={invalid}
        aria-describedby={invalid ? errorId : undefined}
        className={classNames(
          "w-full rounded-sm border bg-surface px-3 py-2 text-ink transition-colors duration-fast ease-standard placeholder:text-muted",
          invalid ? "border-danger" : "border-line-strong",
          className,
        )}
      />
      {invalid ? (
        <p id={errorId} role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
