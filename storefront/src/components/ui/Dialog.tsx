"use client";

/**
 * Wraps `@radix-ui/react-dialog`. This file is the only place the Radix Dialog import
 * lives; `Sheet` and every page reach a modal through `@/components/ui/Dialog`.
 *
 * Hand-rolling the modal is not acceptable here because the parts that make a modal
 * usable are exactly the parts a hand-written one gets wrong, and the failure mode is a
 * keyboard user tabbing into a page that is visually covered: a focus trap, `aria-modal`,
 * the background made inert, Escape routed through a dismissable layer, and scroll locked
 * while the dialog is open. Radix owns those. This file owns the token styling and the
 * prop names.
 *
 * Focus restoration is the one piece Radix does not give us for free: on close it focuses
 * the `Dialog.Trigger` in its own root, and this dialog is controlled from outside with no
 * trigger inside the root, so the trigger ref is null and Radix's default restore is a
 * no-op. We therefore record the element that had focus when the dialog opened and put
 * focus back there ourselves - which is the contract `Sheet` already had.
 */

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useId, useRef, type ReactNode } from "react";
import { Button } from "./Button";
import { classNames } from "./classes";

export type DialogPlacement = "center" | "right";

const PLACEMENT_CLASSES: Record<DialogPlacement, string> = {
  center:
    "left-1/2 top-1/2 max-h-[90vh] w-[min(32rem,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-lg",
  right: "right-0 top-0 h-full w-80 max-w-[85vw] rounded-none",
};

type Props = {
  open: boolean;
  onClose: () => void;
  /** The dialog's accessible name. Rendered as the visible heading and wired through
   * `aria-labelledby`, so the name and the heading can never drift apart. */
  title: string;
  /** The accessible name of the dismiss control. */
  closeLabel: string;
  /** Optional supporting text. When absent the dialog is labelled but not described. */
  description?: string;
  placement?: DialogPlacement;
  className?: string;
  children: ReactNode;
};

function focusedElement(): HTMLElement | null {
  return document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null;
}

export function Dialog({
  open,
  onClose,
  title,
  closeLabel,
  description,
  placement = "center",
  className,
  children,
}: Props) {
  const titleId = useId();
  const descriptionId = useId();
  const openerRef = useRef<HTMLElement | null>(null);

  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          onClose();
        }
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/50" />
        <DialogPrimitive.Content
          aria-labelledby={titleId}
          aria-describedby={
            description === undefined ? undefined : descriptionId
          }
          onOpenAutoFocus={() => {
            // Radix moves focus into the panel immediately after this; the element that
            // still has focus here is the one to return to.
            openerRef.current = focusedElement();
          }}
          onCloseAutoFocus={(event) => {
            // Take the restore over from Radix, whose default targets a trigger this
            // component does not render.
            event.preventDefault();
            openerRef.current?.focus();
          }}
          className={classNames(
            "fixed z-50 flex flex-col gap-4 overflow-y-auto bg-surface p-5 shadow-lg",
            PLACEMENT_CLASSES[placement],
            className,
          )}
        >
          <div className="flex items-center justify-between gap-3">
            <DialogPrimitive.Title
              id={titleId}
              className="font-heading text-lg font-semibold text-ink"
            >
              {title}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="sm">
                {closeLabel}
              </Button>
            </DialogPrimitive.Close>
          </div>
          {description === undefined ? null : (
            <DialogPrimitive.Description
              id={descriptionId}
              className="text-sm text-muted"
            >
              {description}
            </DialogPrimitive.Description>
          )}
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
