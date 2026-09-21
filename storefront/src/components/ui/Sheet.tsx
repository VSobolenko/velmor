"use client";

/**
 * The side drawer: `Dialog` with the panel anchored to the right edge. The Radix import
 * lives in `./Dialog`, so this file names no primitive and a page that opens a drawer
 * still imports only our component.
 *
 * The exported props and the rendering contract are unchanged from the hand-written
 * version this replaces - `open`, `onClose`, `title`, `closeLabel`, `className`,
 * `children` - because `MobileNav` and the header already call it. What changed is that
 * the focus trap, the inert background, Escape and the scroll lock now come from Radix
 * instead of a local keydown listener.
 */

import type { ReactNode } from "react";
import { Dialog } from "./Dialog";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  closeLabel: string;
  className?: string;
  children: ReactNode;
};

export function Sheet({
  open,
  onClose,
  title,
  closeLabel,
  className,
  children,
}: Props) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      closeLabel={closeLabel}
      placement="right"
      className={className}
    >
      {children}
    </Dialog>
  );
}
