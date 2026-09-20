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

export function readCart(): CartLine[] {
  const raw = window.localStorage.getItem(cartStorageKey());
  if (raw === null || raw === "") {
    return [];
  }
  const parsed: unknown = JSON.parse(raw);
  if (!Array.isArray(parsed)) {
    return [];
  }
  return parsed as CartLine[];
}

function writeCart(lines: CartLine[]): void {
  window.localStorage.setItem(cartStorageKey(), JSON.stringify(lines));
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
