/**
 * Proxy route: GET /api/search -> search service /v1/providers/search
 *
 * Requires an active Auth0 session. Forwards all query params upstream.
 * Never exposes the backend service URL to the browser.
 */

import { getSession } from "@auth0/nextjs-auth0";
import { NextRequest, NextResponse } from "next/server";

const SEARCH_SERVICE_URL =
  process.env.SEARCH_SERVICE_URL ?? "http://localhost:8003";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const upstream = new URL(`${SEARCH_SERVICE_URL}/v1/providers/search`);
  for (const [k, v] of searchParams.entries()) {
    upstream.searchParams.set(k, v);
  }

  try {
    const res = await fetch(upstream.toString(), {
      headers: {
        "X-Request-ID":
          req.headers.get("x-request-id") ?? crypto.randomUUID(),
      },
      signal: AbortSignal.timeout(10_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[search-proxy] upstream error:", err);
    return NextResponse.json(
      { error: "Search service unavailable" },
      { status: 502 },
    );
  }
}
