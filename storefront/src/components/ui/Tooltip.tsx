"use client";

/**
 * Wraps `@radix-ui/react-tooltip`. This file is the only place that package is imported;
 * a licence term is explained through `@/components/ui/Tooltip`.
 *
 * A tooltip is not a positioned `div`. Hand-rolling it loses the parts that make it
 * harmless: showing it on pointer hover but never on touch, closing it on a pointer down
 * or Escape, opening it on focus so a keyboard user reaches it, and linking it to the
 * trigger with `aria-describedby`. Radix owns those (verified in the installed source:
 * `onPointerMove` returns early for a touch pointer, `onFocus` opens only when no pointer
 * down is in flight, and the content carries `role="tooltip"`). This file owns the token
 * styling and the prop names.
 *
 * A tooltip is a description, never a name: Radix puts the text in `aria-describedby`, so
 * the trigger's own accessible name has to come from the caller's element. That is what
 * keeps the rule "a tooltip is never the only way information is available" enforceable -
 * if the text were the name, the control would be unlabelled without a pointer.
 */

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

export type TooltipSide = "top" | "right" | "bottom" | "left";

type Props = {
  /** The explanation. Supplementary by contract: the trigger must carry its own name. */
  label: string;
  /** The trigger element. It is given `tabIndex={0}`, so a non-interactive trigger such as
   * an abbreviation is still reachable from the keyboard. */
  children: ReactNode;
  side?: TooltipSide;
};

export function Tooltip({ label, children, side = "top" }: Props) {
  return (
    <TooltipPrimitive.Provider delayDuration={300} skipDelayDuration={0}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild tabIndex={0}>
          {children}
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={4}
            className="z-50 max-w-xs rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink shadow-md"
          >
            {label}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
