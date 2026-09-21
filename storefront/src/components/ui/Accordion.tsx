"use client";

/**
 * Wraps `@radix-ui/react-accordion`. This file is the only place that package is imported;
 * the facts and obligations on a product page reach it through
 * `@/components/ui/Accordion`.
 *
 * Hand-rolling a disclosure is not just a button and a `hidden` block: the trigger needs
 * `aria-expanded` and `aria-controls`, the panel needs `role="region"` and
 * `aria-labelledby` pointing back at the trigger, and the trigger has to be a real button
 * inside a heading so the outline stays navigable. Radix owns that pair of attributes;
 * this file owns the token styling and the prop names.
 *
 * The trigger's accessible name is its own visible text, which is the question itself; the
 * panel takes its name from that same trigger. Section headings render at level three by
 * default, which is the level the product page needs.
 */

import * as AccordionPrimitive from "@radix-ui/react-accordion";
import type { ReactNode } from "react";
import { classNames } from "./classes";

export type AccordionSection = {
  value: string;
  /** The always-visible heading text and the trigger's accessible name. */
  question: string;
  answer: ReactNode;
};

type SharedProps = {
  items: readonly AccordionSection[];
  className?: string;
};

/** `single` keeps one section open at a time; `multiple` lets a buyer open several. */
export type AccordionProps =
  | (SharedProps & {
      type: "single";
      defaultValue: string;
      collapsible?: boolean;
    })
  | (SharedProps & { type: "multiple"; defaultValue: readonly string[] });

const TRIGGER_CLASSES =
  "group tap-target flex w-full items-center justify-between gap-2 py-3 text-left font-medium text-ink";

function Sections({ items }: { items: readonly AccordionSection[] }) {
  return items.map((item) => (
    <AccordionPrimitive.Item
      key={item.value}
      value={item.value}
      className="border-b border-line"
    >
      <AccordionPrimitive.Header>
        <AccordionPrimitive.Trigger className={TRIGGER_CLASSES}>
          {item.question}
          <svg
            aria-hidden="true"
            viewBox="0 0 12 12"
            className="h-3 w-3 shrink-0 stroke-current transition-transform duration-fast ease-standard group-data-[state=open]:rotate-180"
          >
            <path d="M2 4.5 6 8.5 10 4.5" fill="none" strokeWidth="1.5" />
          </svg>
        </AccordionPrimitive.Trigger>
      </AccordionPrimitive.Header>
      <AccordionPrimitive.Content className="pb-3 text-sm text-muted">
        {item.answer}
      </AccordionPrimitive.Content>
    </AccordionPrimitive.Item>
  ));
}

export function Accordion(props: AccordionProps) {
  const { items, className } = props;
  if (props.type === "single") {
    return (
      <AccordionPrimitive.Root
        type="single"
        defaultValue={props.defaultValue}
        collapsible={props.collapsible ?? true}
        className={classNames("w-full", className)}
      >
        <Sections items={items} />
      </AccordionPrimitive.Root>
    );
  }
  return (
    <AccordionPrimitive.Root
      type="multiple"
      defaultValue={[...props.defaultValue]}
      className={classNames("w-full", className)}
    >
      <Sections items={items} />
    </AccordionPrimitive.Root>
  );
}
