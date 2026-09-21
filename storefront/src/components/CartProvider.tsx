"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  addToCart,
  cartSnapshot,
  cartTotal,
  clearCart,
  emptyCartSnapshot,
  removeLine,
  setLineQuantity,
  subscribeCart,
  type CartLine,
} from "@/lib/cart";

export type CartAnnouncements = {
  added: string;
  removed: string;
  quantity: string;
  cleared: string;
};

export type CartValue = {
  lines: CartLine[];
  itemCount: number;
  /** `null` for an empty or mixed-currency cart; see `cartTotal`. */
  total: { amount: string; currency: string } | null;
  add: (line: CartLine) => void;
  remove: (candidateId: string) => void;
  setQuantity: (candidateId: string, quantity: number) => void;
  clear: () => void;
};

const CartContext = createContext<CartValue | null>(null);

type Props = {
  /** Already localised announcement strings, passed from the layout that owns the dictionary. */
  announcements: CartAnnouncements;
  children: ReactNode;
};

/**
 * The one cart store, keyed by the buyer id in `localStorage`. Writes go through
 * `src/lib/cart.ts`, which signals on a window event, so the store, the header badge and the
 * pages that still call `addToCart` directly all read the same state.
 *
 * The `aria-live` region lives here, once, rather than in each component that can change the
 * cart.
 */
export function CartProvider({ announcements, children }: Props) {
  const lines = useSyncExternalStore(
    subscribeCart,
    cartSnapshot,
    emptyCartSnapshot,
  );
  const [message, setMessage] = useState("");

  const announce = useCallback((text: string) => {
    // Setting the same string twice changes nothing in the DOM and announces nothing, so a
    // repeat carries a trailing space and the region mutates again.
    setMessage((current) => (current === text ? `${text} ` : text));
  }, []);

  const add = useCallback(
    (line: CartLine) => {
      addToCart(line);
      announce(announcements.added);
    },
    [announce, announcements.added],
  );

  const remove = useCallback(
    (candidateId: string) => {
      removeLine(candidateId);
      announce(announcements.removed);
    },
    [announce, announcements.removed],
  );

  const setQuantity = useCallback(
    (candidateId: string, quantity: number) => {
      setLineQuantity(candidateId, quantity);
      announce(announcements.quantity);
    },
    [announce, announcements.quantity],
  );

  const clear = useCallback(() => {
    clearCart();
    announce(announcements.cleared);
  }, [announce, announcements.cleared]);

  const value = useMemo<CartValue>(
    () => ({
      lines,
      itemCount: lines.reduce((count, line) => count + line.quantity, 0),
      total: cartTotal(lines),
      add,
      remove,
      setQuantity,
      clear,
    }),
    [lines, add, remove, setQuantity, clear],
  );

  return (
    <CartContext.Provider value={value}>
      <p aria-live="polite" role="status" className="sr-only">
        {message}
      </p>
      {children}
    </CartContext.Provider>
  );
}

/** A consumer outside the provider is a wiring mistake, not an empty cart. */
export function useCart(): CartValue {
  const value = useContext(CartContext);
  if (value === null) {
    throw new Error("useCart must be used inside CartProvider");
  }
  return value;
}
