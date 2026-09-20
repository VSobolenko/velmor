/** Response shapes for the Velmor commerce API (packages/api). */

export type HealthResponse = {
  status: string;
  environment: string;
};

export type CheckoutLineRequest = {
  candidate_id: string;
  unit_amount: string;
  quantity: number;
};

export type CheckoutStartRequest = {
  provider_id: string;
  return_url: string;
  currency: string;
  lines: CheckoutLineRequest[];
};

export type CheckoutStartResponse = {
  order_id: string;
  redirect_url: string;
  provider_reference: string;
  state: string;
};

export type EntitlementState = "active" | "revoked";

export type Entitlement = {
  buyer_id: string;
  candidate_id: string;
  order_id: string;
  granted_at: string;
  state: EntitlementState;
  revocation_reason?: string;
  revoked_at?: string;
};

export type OrderLine = {
  candidate_id: string;
  unit_amount: string;
  quantity: number;
};

export type OrderState =
  | "pending"
  | "paid"
  | "failed"
  | "cancelled"
  | "refunded";

export type Order = {
  order_id: string;
  buyer_id: string;
  state: OrderState;
  currency: string;
  lines: OrderLine[];
  total: string;
  provider_id: string | null;
  provider_reference: string | null;
  created_at: string;
  paid_at: string | null;
};

export type GrantResponse = {
  token: string;
  expires_at: string;
};

export type ApiErrorBody = {
  detail: string;
};

// 6.2 — catalogue browse types (no client functions yet)
export type CatalogueItem = {
  candidate_id: string;
  title: string;
  creator: string | null;
  license_id: string | null;
  landing_url: string;
  download_url: string | null;
};

export type CategorySummary = {
  id: string;
  name: string;
};
