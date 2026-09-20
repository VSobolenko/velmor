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

export type SellerDisclosurePayload = {
  legal_name: string | null;
  registration_number: string | null;
  registration_date: string | null;
  registration_authority: string | null;
  shop_register_number: string | null;
  postal_address: string | null;
  working_hours: string | null;
  contact_details: string | null;
  payment_rules: string | null;
  return_rules: string | null;
  payment_system_marks: string[];
};

export type CheckoutDisclosureResponse = {
  complete: boolean;
  missing: string[];
  disclosure: SellerDisclosurePayload;
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

export type CatalogueGood = {
  candidate_id: string;
  title: string;
  creator: string | null;
  license_id: string | null;
  obligations: string[];
  category_id: string | null;
  category_slug: string | null;
  unit_amount: string;
  currency: string;
};

export type CategorySummary = {
  category_id: string;
  name: string;
  slug: string;
};

export type CategoryDetail = CategorySummary & {
  goods: CatalogueGood[];
};
