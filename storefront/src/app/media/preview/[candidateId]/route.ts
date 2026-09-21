import { NextResponse } from "next/server";

/**
 * Proxies a good's preview from the commerce API.
 *
 * It sits outside `[locale]` because the bytes are the same in every language, and
 * `src/proxy.ts` excludes `media` from locale negotiation so this path is never rewritten.
 *
 * The API's refusal is passed through as a bare status: the storefront shows its own
 * placeholder for any non-200, and the API's detail string is not written for a buyer.
 * Nothing here names the origin.
 */
export const dynamic = "force-dynamic";

const API_BASE_URL_ENV = "NEXT_PUBLIC_VELMOR_API_URL";

function apiBaseUrl(): string {
  const value = process.env[API_BASE_URL_ENV];
  if (value === undefined || value === "") {
    throw new Error(`${API_BASE_URL_ENV} is required`);
  }
  return value.replace(/\/$/, "");
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ candidateId: string }> },
): Promise<NextResponse> {
  const { candidateId } = await params;
  // The bytes for a candidate id are immutable, so an explicit `force-cache` replaces the
  // refetch this route used to perform on every card render.
  const upstream = await fetch(
    `${apiBaseUrl()}/catalogue/goods/${encodeURIComponent(candidateId)}/preview`,
    { cache: "force-cache" },
  );

  if (!upstream.ok) {
    return new NextResponse(null, { status: upstream.status });
  }

  const headers = new Headers();
  for (const name of ["content-type", "etag", "cache-control"]) {
    const value = upstream.headers.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }
  return new NextResponse(await upstream.arrayBuffer(), { status: 200, headers });
}
