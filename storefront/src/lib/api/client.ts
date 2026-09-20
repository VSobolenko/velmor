import type {
  CatalogueGood,
  CategoryDetail,
  CategorySummary,
  CheckoutDisclosureResponse,
  CheckoutStartRequest,
  CheckoutStartResponse,
  Entitlement,
  GrantResponse,
  HealthResponse,
  Order,
} from "./types";

const BUYER_HEADER = "X-Buyer-Id";

export class CommerceApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "CommerceApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class CommerceApiClient {
  private readonly baseUrl: string;
  private readonly buyerId: string;

  constructor(baseUrl: string, buyerId: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.buyerId = buyerId;
  }

  static fromEnv(): CommerceApiClient {
    const baseUrl = process.env.NEXT_PUBLIC_VELMOR_API_URL;
    const buyerId = process.env.NEXT_PUBLIC_BUYER_ID;
    if (baseUrl === undefined || baseUrl === "") {
      throw new Error("NEXT_PUBLIC_VELMOR_API_URL is required");
    }
    if (buyerId === undefined || buyerId === "") {
      throw new Error("NEXT_PUBLIC_BUYER_ID is required");
    }
    return new CommerceApiClient(baseUrl, buyerId);
  }

  async getHealth(): Promise<HealthResponse> {
    return this.requestJson<HealthResponse>("GET", "/health", false);
  }

  async listCategories(): Promise<CategorySummary[]> {
    return this.requestJson<CategorySummary[]>(
      "GET",
      "/catalogue/categories",
      false,
    );
  }

  async getCategory(slug: string): Promise<CategoryDetail> {
    return this.requestJson<CategoryDetail>(
      "GET",
      `/catalogue/categories/${encodeURIComponent(slug)}`,
      false,
    );
  }

  async listGoods(): Promise<CatalogueGood[]> {
    return this.requestJson<CatalogueGood[]>("GET", "/catalogue/goods", false);
  }

  async getGood(candidateId: string): Promise<CatalogueGood> {
    return this.requestJson<CatalogueGood>(
      "GET",
      `/catalogue/goods/${encodeURIComponent(candidateId)}`,
      false,
    );
  }

  async getCheckoutDisclosure(): Promise<CheckoutDisclosureResponse> {
    return this.requestJson<CheckoutDisclosureResponse>(
      "GET",
      "/checkout/disclosure",
      false,
    );
  }

  async startCheckout(
    body: CheckoutStartRequest,
  ): Promise<CheckoutStartResponse> {
    return this.requestJson<CheckoutStartResponse>(
      "POST",
      "/checkout/start",
      true,
      body,
    );
  }

  async listEntitlements(): Promise<Entitlement[]> {
    return this.requestJson<Entitlement[]>("GET", "/account/entitlements", true);
  }

  async listOrders(): Promise<Order[]> {
    return this.requestJson<Order[]>("GET", "/account/orders", true);
  }

  async getOrder(orderId: string): Promise<Order> {
    return this.requestJson<Order>(
      "GET",
      `/account/orders/${encodeURIComponent(orderId)}`,
      true,
    );
  }

  async issueGrant(candidateId: string): Promise<GrantResponse> {
    return this.requestJson<GrantResponse>(
      "POST",
      `/account/goods/${encodeURIComponent(candidateId)}/grant`,
      true,
    );
  }

  /** Absolute URL for the download grant endpoint (needs X-Buyer-Id). */
  downloadUrl(token: string): string {
    return `${this.baseUrl}/downloads/${encodeURIComponent(token)}`;
  }

  /**
   * Fetch granted bytes with the buyer header and trigger a browser save.
   * A bare navigation to {@link downloadUrl} cannot send X-Buyer-Id.
   */
  async saveDownload(token: string, filename: string): Promise<void> {
    const response = await fetch(this.downloadUrl(token), {
      method: "GET",
      headers: { [BUYER_HEADER]: this.buyerId },
      cache: "no-store",
    });
    if (!response.ok) {
      const detail = await this.readErrorDetail(response);
      throw new CommerceApiError(response.status, detail);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  }

  private async requestJson<T>(
    method: string,
    path: string,
    withBuyer: boolean,
    body?: unknown,
  ): Promise<T> {
    const headers: Record<string, string> = {};
    if (withBuyer) {
      headers[BUYER_HEADER] = this.buyerId;
    }
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    if (!response.ok) {
      const detail = await this.readErrorDetail(response);
      throw new CommerceApiError(response.status, detail);
    }
    return (await response.json()) as T;
  }

  private async readErrorDetail(response: Response): Promise<string> {
    const text = await response.text();
    if (text === "") {
      return `HTTP ${response.status}`;
    }
    if (!text.startsWith("{")) {
      return text;
    }
    const parsed: unknown = JSON.parse(text);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof (parsed as { detail: unknown }).detail === "string"
    ) {
      return (parsed as { detail: string }).detail;
    }
    return text;
  }
}
