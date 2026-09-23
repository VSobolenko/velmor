import type { Locale } from "@/lib/i18n";
import type {
  CatalogueCard,
  CataloguePage,
  CatalogueQuery,
  CategoryPage,
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

/**
 * How the API answered a non-2xx status.
 *
 * `refusal` is a documented business response: `detail` is a sentence the API wrote for a
 * person and the storefront may show it. `fault` is a validation rejection (422) or a server
 * fault (5xx), and also any body that is not the API's `{"detail": string}` envelope: its
 * `detail` is a diagnostic for logs and the caller must render a localized generic message
 * instead of showing it.
 */
export type CommerceApiFailure = "refusal" | "fault";

type ReadFailure = { detail: string; reason: CommerceApiFailure };

export class CommerceApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly reason: CommerceApiFailure;

  constructor(status: number, detail: string, reason: CommerceApiFailure) {
    super(detail);
    this.name = "CommerceApiError";
    this.status = status;
    this.detail = detail;
    this.reason = reason;
  }
}

export class CommerceApiClient {
  private readonly baseUrl: string;
  private readonly buyerId: string;
  private readonly locale: Locale;

  constructor(baseUrl: string, buyerId: string, locale: Locale) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.buyerId = buyerId;
    this.locale = locale;
  }

  static fromEnv(locale: Locale): CommerceApiClient {
    const baseUrl = process.env.NEXT_PUBLIC_VELMOR_API_URL;
    const buyerId = process.env.NEXT_PUBLIC_BUYER_ID;
    if (baseUrl === undefined || baseUrl === "") {
      throw new Error("NEXT_PUBLIC_VELMOR_API_URL is required");
    }
    if (buyerId === undefined || buyerId === "") {
      throw new Error("NEXT_PUBLIC_BUYER_ID is required");
    }
    return new CommerceApiClient(baseUrl, buyerId, locale);
  }

  /**
   * The API never negotiates: the storefront owns the locale and sends it, so a cached
   * response cannot be handed to a reader of another language. An empty or absent value is
   * left out rather than sent, so `?q=` never reads as a search for the empty string.
   */
  private cataloguePath(
    path: string,
    query: Record<string, string | number | undefined>,
  ): string {
    const params = new URLSearchParams({ locale: this.locale });
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== "") {
        params.set(key, String(value));
      }
    }
    return `${path}?${params.toString()}`;
  }

  async getHealth(): Promise<HealthResponse> {
    return this.requestJson<HealthResponse>("GET", "/health", false);
  }

  async listCategories(): Promise<CategorySummary[]> {
    return this.requestJson<CategorySummary[]>(
      "GET",
      this.cataloguePath("/catalogue/categories", {}),
      false,
    );
  }

  async getCategory(
    slug: string,
    query: Pick<CatalogueQuery, "limit" | "offset"> = {},
  ): Promise<CategoryPage> {
    return this.requestJson<CategoryPage>(
      "GET",
      this.cataloguePath(`/catalogue/categories/${encodeURIComponent(slug)}`, {
        limit: query.limit,
        offset: query.offset,
      }),
      false,
    );
  }

  async listGoods(query: CatalogueQuery = {}): Promise<CataloguePage> {
    return this.requestJson<CataloguePage>(
      "GET",
      this.cataloguePath("/catalogue/goods", {
        q: query.q,
        sort: query.sort,
        category: query.category,
        license: query.license,
        limit: query.limit,
        offset: query.offset,
      }),
      false,
    );
  }

  /**
   * `candidateId` is a value already valid as a URL path segment, so it is placed as-is.
   *
   * Encoding it here is what broke this surface. A `[candidateId]` segment reaches a `page.tsx`
   * undecoded while a `route.ts` receives it decoded (vercel/next.js#64952, "pathParam is
   * undecoded when used from page.tsx and useParams() but is decoded when used from route.ts"),
   * so the product page already holds `openverse%3A...`. Encoding that again sent
   * `openverse%253A...`, which the API answers with 404, and every product page failed: the page
   * where a buyer buys. A caller holding a raw id from API JSON, as the account pages do, makes it
   * a segment with `encodeURIComponent` at the call site.
   */
  async getGood(candidateId: string): Promise<CatalogueCard> {
    return this.requestJson<CatalogueCard>(
      "GET",
      this.cataloguePath(`/catalogue/goods/${candidateId}`, {}),
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

  async listCheckoutProviders(): Promise<string[]> {
    return this.requestJson<string[]>("GET", "/checkout/providers", false);
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
      const failure = await this.readFailure(response);
      throw new CommerceApiError(response.status, failure.detail, failure.reason);
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
      const failure = await this.readFailure(response);
      throw new CommerceApiError(response.status, failure.detail, failure.reason);
    }
    return (await response.json()) as T;
  }

  /**
   * Classifies a non-2xx body. A 422 (FastAPI validation) or a 5xx is a fault, and so is any
   * body that is not the API's JSON envelope: those are machine payloads and a caller must not
   * print them. Only a `{"detail": "<sentence>"}` on a non-fault status is a refusal the
   * storefront may show as written.
   */
  private async readFailure(response: Response): Promise<ReadFailure> {
    const text = await response.text();
    const status = `HTTP ${response.status}`;
    if (!text.startsWith("{")) {
      return {
        detail: text === "" ? status : text,
        reason: "fault",
      };
    }
    const message = this.stringDetail(JSON.parse(text));
    if (
      response.status === 422 ||
      response.status >= 500 ||
      message === null
    ) {
      return { detail: message ?? status, reason: "fault" };
    }
    return { detail: message, reason: "refusal" };
  }

  /** The API's human-readable message, or `null` when `detail` is a machine payload. */
  private stringDetail(parsed: unknown): string | null {
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof (parsed as { detail: unknown }).detail === "string"
    ) {
      return (parsed as { detail: string }).detail;
    }
    return null;
  }
}
