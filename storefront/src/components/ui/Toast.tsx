"use client";

/**
 * Wraps `@radix-ui/react-toast`. This file is the only place that package is imported;
 * the "added to cart" confirmation reaches a toast through `useToast()` from
 * `@/components/ui/Toast`.
 *
 * The live region is the part that is easy to get wrong. A region that is inserted
 * together with its text is not reliably announced - the region has to exist before the
 * update - and a region per toast means several regions competing for the same
 * announcement. This provider therefore keeps exactly one toast slot and lets Radix render
 * the single polite region for it: `Toast.Provider` owns it, its label comes from the
 * `announceLabel` prop, and it is `role="status"` with `aria-live="polite"` (verified in
 * the installed source for `type="background"`, which this component sets). We add no
 * `aria-live` element of our own, because a second one is a defect rather than a belt.
 *
 * Auto-dismiss is pausable without any work from us: Radix's viewport dispatches a pause
 * on pointer move and on focus and resumes on pointer leave and focus out (verified in
 * the installed source), and the close control makes the timing adjustable without a
 * pointer. There is no entry or exit animation, so there is no motion to switch off under
 * `prefers-reduced-motion`; the message is carried by the text, never by a transition.
 */

import * as ToastPrimitive from "@radix-ui/react-toast";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type ToastRequest = {
  /** The line a buyer reads, and the text the live region announces. */
  title: string;
  /** Optional second line. */
  description?: string;
};

type ToastItem = ToastRequest & { id: number };

export type ToastValue = {
  /** Replaces any toast already on screen. */
  show: (toast: ToastRequest) => void;
  /** Dismisses the toast on screen, if there is one. */
  dismiss: () => void;
};

const ToastContext = createContext<ToastValue | null>(null);

type Props = {
  /** Radix prefixes each announcement with this, so the interruption is identified as a
   * notification rather than read as page content. */
  announceLabel: string;
  /** The accessible name of the region the toasts appear in. */
  regionLabel: string;
  /** The accessible name of the dismiss control. */
  closeLabel: string;
  /** How long a toast stays before it dismisses itself. Optional by design: this is a
   * tuning value with a sensible length, not a decision the caller has to make. */
  duration?: number;
  children: ReactNode;
};

export function ToastProvider({
  announceLabel,
  regionLabel,
  closeLabel,
  duration = 5000,
  children,
}: Props) {
  const [toast, setToast] = useState<ToastItem | null>(null);
  const lastIdRef = useRef(0);

  const show = useCallback((next: ToastRequest) => {
    lastIdRef.current += 1;
    setToast({ ...next, id: lastIdRef.current });
  }, []);

  const dismiss = useCallback(() => setToast(null), []);

  const value = useMemo<ToastValue>(
    () => ({ show, dismiss }),
    [show, dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      <ToastPrimitive.Provider label={announceLabel}>
        {children}
        {toast === null ? null : (
          // The key restarts the dismiss timer when a new message replaces the old one.
          <ToastPrimitive.Root
            key={toast.id}
            type="background"
            duration={duration}
            onOpenChange={(open) => {
              if (!open) {
                setToast(null);
              }
            }}
            className="flex w-full items-start gap-3 rounded-md border border-line bg-surface p-3 shadow-lg"
          >
            <div className="flex flex-col gap-1">
              <ToastPrimitive.Title className="text-sm font-medium text-ink">
                {toast.title}
              </ToastPrimitive.Title>
              {toast.description === undefined ? null : (
                <ToastPrimitive.Description className="text-sm text-muted">
                  {toast.description}
                </ToastPrimitive.Description>
              )}
            </div>
            <ToastPrimitive.Close
              aria-label={closeLabel}
              className="tap-target ml-auto flex shrink-0 items-center justify-center rounded-sm text-muted"
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 12 12"
                className="h-3 w-3 stroke-current"
              >
                <path
                  d="M3 3 9 9 M9 3 3 9"
                  fill="none"
                  strokeWidth="1.5"
                />
              </svg>
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        )}
        <ToastPrimitive.Viewport
          label={regionLabel}
          className="fixed bottom-0 right-0 z-50 flex w-full max-w-sm flex-col gap-2 p-4"
        />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

/** A consumer outside the provider is a wiring mistake, not a silent no-op. */
export function useToast(): ToastValue {
  const value = useContext(ToastContext);
  if (value === null) {
    throw new Error("useToast must be used inside ToastProvider");
  }
  return value;
}
