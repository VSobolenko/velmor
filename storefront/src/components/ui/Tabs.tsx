"use client";

/**
 * Wraps `@radix-ui/react-tabs`. This file is the only place that package is imported; a
 * view switch reaches tabs through `@/components/ui/Tabs`.
 *
 * Hand-rolling tabs gets the visible part right and the wiring wrong: `role="tablist"` /
 * `role="tab"` / `role="tabpanel"` with `aria-selected`, `aria-controls` on the tab and
 * `aria-labelledby` on the panel, arrow keys that move between tabs while Tab leaves the
 * list, and roving tabindex so the whole strip is one stop. Radix owns that; this file
 * owns the token styling and the prop names.
 *
 * The tab list's accessible name comes from the `label` prop; each tab's name is its own
 * visible text, which Radix does not override. The panel takes its name from the tab that
 * controls it, so the two can never drift apart.
 */

import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ReactNode } from "react";
import { classNames } from "./classes";

export type TabItem = {
  value: string;
  label: string;
  content: ReactNode;
};

type Props = {
  /** The tab list's accessible name, so a buyer is told which strip of tabs this is. */
  label: string;
  items: readonly TabItem[];
  /** The tab that is open when the strip first renders. Required, so a strip is never
   * mounted with no panel showing. */
  defaultValue: string;
  /** Set together with `onValueChange` to control the selection from outside. */
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
};

export function Tabs({
  label,
  items,
  defaultValue,
  value,
  onValueChange,
  className,
}: Props) {
  return (
    <TabsPrimitive.Root
      defaultValue={defaultValue}
      value={value}
      onValueChange={onValueChange}
      className={className}
    >
      <TabsPrimitive.List
        aria-label={label}
        className="flex flex-wrap gap-1 border-b border-line"
      >
        {items.map((item) => (
          <TabsPrimitive.Trigger
            key={item.value}
            value={item.value}
            className={classNames(
              "tap-target inline-flex items-center rounded-t-md border-b-2 border-transparent px-3 py-2 text-sm font-medium text-muted",
              "data-[state=active]:border-accent-strong data-[state=active]:text-ink",
            )}
          >
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {items.map((item) => (
        <TabsPrimitive.Content
          key={item.value}
          value={item.value}
          className="pt-4"
        >
          {item.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}
