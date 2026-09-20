export const CART_STORAGE_KEY = "velmor.cart";

export type CartLine = {
  candidate_id: string;
  unit_amount: string;
  quantity: number;
  currency: string;
  title: string;
};

export function readCart(): CartLine[] {
  const raw = window.localStorage.getItem(CART_STORAGE_KEY);
  if (raw === null || raw === "") {
    return [];
  }
  const parsed: unknown = JSON.parse(raw);
  if (!Array.isArray(parsed)) {
    return [];
  }
  return parsed as CartLine[];
}

export function addToCart(line: CartLine): void {
  const lines = readCart().filter(
    (existing) => existing.candidate_id !== line.candidate_id,
  );
  lines.push(line);
  window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(lines));
}
