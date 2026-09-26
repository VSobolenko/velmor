/** Response shapes for the Velmor commerce API (packages/api). */

export type HealthResponse = {
  status: string;
  environment: string;
};

/** The signed-in buyer, as `/auth/me` and the auth routes return it. Never carries a password. */
export type BuyerProfile = {
  id: string;
  email: string;
  display_name: string;
};

export type RegisterRequest = {
  email: string;
  password: string;
  display_name: string;
};

export type SignInRequest = {
  email: string;
  password: string;
};

export type ChangePasswordRequest = {
  current_password: string;
  new_password: string;
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

export type OrderState = "pending" | "paid" | "failed" | "cancelled" | "refunded";

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
  /** English prose the API wrote for logs and developers; never rendered to a buyer. */
  detail: string;
  /** The stable machine code the storefront maps to a locale key. */
  reason?: string;
  /** Present on `password_too_short`: the API-owned minimum password length. */
  minimum_length?: number;
};

/**
 * One good as a buyer sees it. Frozen by `.superpowers/sdd/redesign-storefront-ux/contract.md`.
 *
 * `origin_url`, `content_digest` and any storage path are forbidden in this shape: the origin
 * is internal and a buyer-facing payload must never carry it.
 */
export type CatalogueCard = {
  candidate_id: string;
  /** Resolved for the requested locale: presentation, then `ru`, then a shortened source title. */
  title: string;
  /** Always the raw source title, whatever the locale. */
  original_title: string;
  summary: string | null;
  creator: string | null;
  license_id: string | null;
  /** Every obligation recorded for the good, shown before purchase. */
  obligations: string[];
  category_id: string | null;
  category_slug: string | null;
  unit_amount: string;
  currency: string;
  /** The API path; the storefront shows the good through `/media/preview/{candidate_id}`. */
  preview_url: string;
  preview_is_cover: boolean;
  content_type: string;
  /**
   * `null` when the source never reported a size, which is not the same as zero and must not be
   * rendered as a number: `catalogue_card.py` states that claiming a size we do not have is worse
   * than stating that it is unknown. Typing this `number` is what let the storefront print
   * "0 byte" for an unknown file on most of the catalogue, so the type carries the null.
   */
  size_bytes: number | null;
  published_at: string;
};

export type CataloguePage = {
  items: CatalogueCard[];
  /** Every match, not the page. */
  total: number;
  limit: number;
  offset: number;
};

export type CatalogueSort =
  | "newest"
  | "price_asc"
  | "price_desc"
  | "title_asc"
  | "title_desc";

export type CatalogueQuery = {
  q?: string;
  sort?: CatalogueSort;
  category?: string;
  license?: string;
  limit?: number;
  offset?: number;
};

export type CategorySummary = {
  category_id: string;
  name: string;
  slug: string;
  /** Saleable goods in the category. */
  count: number;
};

export type CategoryPage = CategorySummary & {
  items: CatalogueCard[];
  total: number;
};
