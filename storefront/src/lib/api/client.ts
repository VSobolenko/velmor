import type { Locale } from "@/lib/i18n";
import type {
  BuyerProfile,
  CatalogueCard,
  CataloguePage,
  CatalogueQuery,
  CategoryPage,
  CategorySummary,
  ChangePasswordRequest,
  CheckoutDisclosureResponse,
  CheckoutStartRequest,
  CheckoutStartResponse,
  Entitlement,
  GrantResponse,
  HealthResponse,
  Order,
  RegisterRequest,
  SignInRequest,
} from "./types";

/**
 * How the API answered a non-2xx status.
 *
 * `refusal` is a documented business response. `fault` is a validation rejection (422), a
 * server fault (5xx), or any body that is not the API's JSON envelope.
 */
export type CommerceApiFailure = "refusal" | "fault";

/**
 * The stable machine codes the API returns on a refusal. The storefront switches on one of
 * these to choose a locale key. The `detail` string beside a code is a sentence the API wrote
 * for logs and developers, and is never rendered to a buyer.
 */
export type CommerceApiRefusalReason =
  | "email_required"
  | "email_unavailable"
  | "invalid_credentials"
  | "password_too_short"
  | "current_password_incorrect"
  | "rate_limited"
  | "unauthenticated";

const REFUSAL_REASONS: readonly CommerceApiRefusalReason[] = [
  "email_required",
  "email_unavailable",
  "invalid_credentials",
  "password_too_short",
  "current_password_incorrect",
  "rate_limited",
  "unauthenticated",
];

/**
 * A refusal code, `refusal` when the API sent no recognised code, or `fault` for a non-refusal
 * answer. A code the storefront does not recognise falls back to a generic localized message.
 */
export type CommerceApiReason = CommerceApiFailure | CommerceApiRefusalReason;

type ReadFailure = {
  detail: string;
  reason: CommerceApiReason;
  minimumLength: number | null;
};

export class CommerceApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly reason: CommerceApiReason;
  /** The API-owned minimum password length, present only on `password_too_short`. */
  readonly minimumLength: number | null;

  constructor(
    status: number,
    detail: string,
    reason: CommerceApiReason,
    minimumLength: number | null = null,
  ) {
    super(detail);
    this.name = "CommerceApiError";
    this.status = status;
    this.detail = detail;
    this.reason = reason;
    this.minimumLength = minimumLength;
  }
}

export class CommerceApiClient {
  private readonly baseUrl: string;
  private readonly locale: Locale;
  private readonly cookie: string | null;

  private constructor(baseUrl: string, locale: Locale, cookie: string | null) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.locale = locale;
    this.cookie = cookie;
  }

  /**
   * A browser client. The base is the shop's own origin, so the session cookie the API set is
   * sent first-party and automatically: a same-origin request needs no `credentials` option,
   * and no buyer-identifying header exists any more.
   */
  static fromEnv(locale: Locale): CommerceApiClient {
    return new CommerceApiClient("/api", locale, null);
  }

  /**
   * A server client. `cookie` is the caller's `Cookie` header, resolved with `cookies()` by
   * `api/server.ts`, because a `fetch` made on the Next server does not run in the browser and
   * therefore carries no cookie of its own. Without it every account page renders signed out.
   *
   * `baseUrl` is absolute: a server-side `fetch` cannot resolve a relative `/api`.
   */
  static fromServer(
    baseUrl: string,
    locale: Locale,
    cookie: string,
  ): CommerceApiClient {
    return new CommerceApiClient(baseUrl, locale, cookie);
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
    return this.requestJson<HealthResponse>("GET", "/health");
  }

  async listCategories(): Promise<CategorySummary[]> {
    return this.requestJson<CategorySummary[]>(
      "GET",
      this.cataloguePath("/catalogue/categories", {}),
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
    );
  }

  async getCheckoutDisclosure(): Promise<CheckoutDisclosureResponse> {
    return this.requestJson<CheckoutDisclosureResponse>(
      "GET",
      "/checkout/disclosure",
    );
  }

  async listCheckoutProviders(): Promise<string[]> {
    return this.requestJson<string[]>("GET", "/checkout/providers");
  }

  async startCheckout(
    body: CheckoutStartRequest,
  ): Promise<CheckoutStartResponse> {
    return this.requestJson<CheckoutStartResponse>(
      "POST",
      "/checkout/start",
      body,
    );
  }

  async register(body: RegisterRequest): Promise<BuyerProfile> {
    return this.requestJson<BuyerProfile>("POST", "/auth/register", body);
  }

  async signIn(body: SignInRequest): Promise<BuyerProfile> {
    return this.requestJson<BuyerProfile>("POST", "/auth/session", body);
  }

  async signOut(): Promise<void> {
    await this.requestEmpty("DELETE", "/auth/session");
  }

  async getProfile(): Promise<BuyerProfile> {
    return this.requestJson<BuyerProfile>("GET", "/auth/me");
  }

  async changePassword(body: ChangePasswordRequest): Promise<void> {
    await this.requestEmpty("POST", "/auth/password", body);
  }

  async listEntitlements(): Promise<Entitlement[]> {
    return this.requestJson<Entitlement[]>("GET", "/account/entitlements");
  }

  async listOrders(): Promise<Order[]> {
    return this.requestJson<Order[]>("GET", "/account/orders");
  }

  async getOrder(orderId: string): Promise<Order> {
    return this.requestJson<Order>(
      "GET",
      `/account/orders/${encodeURIComponent(orderId)}`,
    );
  }

  async issueGrant(candidateId: string): Promise<GrantResponse> {
    return this.requestJson<GrantResponse>(
      "POST",
      `/account/goods/${encodeURIComponent(candidateId)}/grant`,
    );
  }

  /** The grant download address, on the shop's own origin so the session cookie reaches it. */
  downloadUrl(token: string): string {
    return `${this.baseUrl}/downloads/${encodeURIComponent(token)}`;
  }

  /**
   * Fetch granted bytes and trigger a browser save. The request carries the session cookie,
   * which a same-origin call sends automatically; the `X-Buyer-Id` header this once set is gone
   * with the header itself.
   */
  async saveDownload(token: string, filename: string): Promise<void> {
    const response = await this.request(
      "GET",
      `/downloads/${encodeURIComponent(token)}`,
    );
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  }

  private async request(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<Response> {
    const headers: Record<string, string> = {};
    if (this.cookie !== null) {
      // The server path: the browser's cookie does not travel on its own, so it is attached
      // here. The browser path leaves it out and the same-origin request carries it anyway.
      headers.Cookie = this.cookie;
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
      throw new CommerceApiError(
        response.status,
        failure.detail,
        failure.reason,
        failure.minimumLength,
      );
    }
    return response;
  }

  private async requestJson<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const response = await this.request(method, path, body);
    return (await response.json()) as T;
  }

  /** A route that answers with no body, such as signing out. */
  private async requestEmpty(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<void> {
    await this.request(method, path, body);
  }

  /**
   * Classifies a non-2xx body. A 422 (FastAPI validation) or a 5xx is a fault, and so is any
   * body that is not the API's JSON envelope: those are machine payloads and a caller must not
   * print them. A documented refusal carries a stable `reason` code, which is what a caller
   * maps to a locale key in place of the `detail` sentence beside it.
   */
  private async readFailure(response: Response): Promise<ReadFailure> {
    const text = await response.text();
    const status = `HTTP ${response.status}`;
    if (!text.startsWith("{")) {
      return {
        detail: text === "" ? status : text,
        reason: "fault",
        minimumLength: null,
      };
    }
    const parsed: unknown = JSON.parse(text);
    const message = this.stringDetail(parsed);
    if (
      response.status === 422 ||
      response.status >= 500 ||
      message === null
    ) {
      return { detail: message ?? status, reason: "fault", minimumLength: null };
    }
    return {
      detail: message,
      reason: this.refusalReason(parsed) ?? "refusal",
      minimumLength: this.minimumLengthOf(parsed),
    };
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

  /** The API's stable refusal code, or `null` when it sent none or one this build does not know. */
  private refusalReason(parsed: unknown): CommerceApiRefusalReason | null {
    if (typeof parsed !== "object" || parsed === null || !("reason" in parsed)) {
      return null;
    }
    const value = (parsed as { reason: unknown }).reason;
    if (typeof value !== "string") {
      return null;
    }
    return REFUSAL_REASONS.find((reason) => reason === value) ?? null;
  }

  /** The API-owned minimum password length, or `null` when this refusal does not carry one. */
  private minimumLengthOf(parsed: unknown): number | null {
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      !("minimum_length" in parsed)
    ) {
      return null;
    }
    const value = (parsed as { minimum_length: unknown }).minimum_length;
    return typeof value === "number" && Number.isInteger(value) ? value : null;
  }
}
