export type CartLine = {
  candidate_id: string;
  unit_amount: string;
  quantity: number;
  currency: string;
  title: string;
};

function buyerId(): string {
  const value = process.env.NEXT_PUBLIC_BUYER_ID;
  if (value === undefined || value === "") {
    throw new Error("NEXT_PUBLIC_BUYER_ID is required");
  }
  return value;
}

/** Buyer-scoped key so demo buyers do not share a cart. */
export function cartStorageKey(): string {
  return `velmor.cart.${buyerId()}`;
}

const DECIMAL_AMOUNT = /^-?\d+(\.\d+)?$/;

/**
 * The stored text is untrusted: any script on the page can write it, and it survives a deploy
 * of an older line shape. A value that is not exactly what the checkout posts is dropped
 * rather than cast, so a wrong entry cannot reach `/checkout/start` as `undefined` or throw
 * inside `cartTotal` during a render.
 */
function isCartLine(value: unknown): value is CartLine {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const line = value as Record<string, unknown>;
  return (
    typeof line.candidate_id === "string" &&
    line.candidate_id !== "" &&
    typeof line.unit_amount === "string" &&
    DECIMAL_AMOUNT.test(line.unit_amount) &&
    typeof line.quantity === "number" &&
    Number.isInteger(line.quantity) &&
    line.quantity >= 1 &&
    typeof line.currency === "string" &&
    line.currency !== "" &&
    typeof line.title === "string" &&
    line.title !== ""
  );
}

export function readCart(): CartLine[] {
  const raw = window.localStorage.getItem(cartStorageKey());
  if (raw === null || raw === "") {
    return [];
  }
  const parsed: unknown = JSON.parse(raw);
  if (!Array.isArray(parsed)) {
    return [];
  }
  return parsed.filter(isCartLine);
}

/** Same-tab signal: the `storage` event only fires in the other tabs. */
const CART_EVENT = "velmor.cart.changed";

function writeCart(lines: CartLine[]): void {
  window.localStorage.setItem(cartStorageKey(), JSON.stringify(lines));
  window.dispatchEvent(new Event(CART_EVENT));
}

/** The same-tab event plus `storage`, which covers a second tab writing the cart. */
export function subscribeCart(listener: () => void): () => void {
  window.addEventListener(CART_EVENT, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(CART_EVENT, listener);
    window.removeEventListener("storage", listener);
  };
}

const EMPTY_CART: CartLine[] = [];

/** The server snapshot: `useSyncExternalStore` needs one array identity it can trust. */
export function emptyCartSnapshot(): CartLine[] {
  return EMPTY_CART;
}

let snapshotRaw: string | null = null;
let snapshotLines: CartLine[] = EMPTY_CART;

/**
 * The client snapshot, reparsed only when the stored text changes, so the reference stays
 * stable between renders and `useSyncExternalStore` does not loop.
 */
export function cartSnapshot(): CartLine[] {
  const raw = window.localStorage.getItem(cartStorageKey()) ?? "";
  if (raw !== snapshotRaw) {
    snapshotRaw = raw;
    snapshotLines = raw === "" ? EMPTY_CART : readCart();
  }
  return snapshotLines;
}

export function clearCart(): void {
  window.localStorage.removeItem(cartStorageKey());
  window.dispatchEvent(new Event(CART_EVENT));
}

export function addToCart(line: CartLine): void {
  const lines = readCart().filter(
    (existing) => existing.candidate_id !== line.candidate_id,
  );
  lines.push(line);
  writeCart(lines);
}

export function setLineQuantity(candidateId: string, quantity: number): void {
  if (quantity < 1) {
    removeLine(candidateId);
    return;
  }
  const lines = readCart().map((line) =>
    line.candidate_id === candidateId ? { ...line, quantity } : line,
  );
  writeCart(lines);
}

export function removeLine(candidateId: string): void {
  writeCart(readCart().filter((line) => line.candidate_id !== candidateId));
}

type Scaled = {
  units: number;
  scale: number;
};

/** `"9.99"` becomes 999 at scale 2; the digits are never put through a float. */
function scaledAmount(amount: string): Scaled {
  const [whole = "", fraction = ""] = amount.split(".");
  const fractionDigits = fraction.replace(/[^0-9]/g, "");
  const wholeDigits = whole.replace(/[^0-9]/g, "");
  if (wholeDigits === "" && fractionDigits === "") {
    throw new Error(`Not a decimal amount: ${amount}`);
  }
  const sign = whole.startsWith("-") ? "-" : "";
  return {
    units: Number.parseInt(`${sign}${wholeDigits}${fractionDigits}`, 10),
    scale: fractionDigits.length,
  };
}

function scaleUp(units: number, from: number, to: number): number {
  return units * 10 ** (to - from);
}

function formatScaled({ units, scale }: Scaled): string {
  if (scale === 0) {
    return String(units);
  }
  const digits = String(Math.abs(units)).padStart(scale + 1, "0");
  const cut = digits.length - scale;
  const sign = units < 0 ? "-" : "";
  return `${sign}${digits.slice(0, cut)}.${digits.slice(cut)}`;
}

/**
 * The display total, summed as scaled integers. `null` when there is nothing to total or
 * when the lines hold more than one currency: the checkout refuses a mixed cart, and a
 * single number across two currencies would be a lie. The authoritative total for a paid
 * order is the one the API returns.
 */
export function cartTotal(
  lines: CartLine[],
): { amount: string; currency: string } | null {
  if (lines.length === 0) {
    return null;
  }
  const currency = lines[0].currency;
  if (!lines.every((line) => line.currency === currency)) {
    return null;
  }
  const scaled = lines.map((line) => scaledAmount(line.unit_amount));
  const scale = scaled.reduce(
    (widest, entry) => Math.max(widest, entry.scale),
    0,
  );
  let units = 0;
  for (let index = 0; index < lines.length; index += 1) {
    units +=
      scaleUp(scaled[index].units, scaled[index].scale, scale) *
      lines[index].quantity;
  }
  return { amount: formatScaled({ units, scale }), currency };
}
