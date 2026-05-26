/**
 * Proxy route: GET /api/reports/[id] -> report service /v1/reports/{id}
 *
 * Requires an active Auth0 session.
 * Used for status polling and fetching completed report HTML.
 */

import { getSession } from "@auth0/nextjs-auth0";
import { NextRequest, NextResponse } from "next/server";

const REPORT_SERVICE_URL =
  process.env.REPORT_SERVICE_URL ?? "http://localhost:8004";

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = params;

  try {
    const res = await fetch(`${REPORT_SERVICE_URL}/v1/reports/${id}`, {
      signal: AbortSignal.timeout(10_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[reports-proxy] upstream error:", err);
    return NextResponse.json(
      { error: "Report service unavailable" },
      { status: 502 },
    );
  }
}
