/**
 * Proxy route: POST /api/reports -> report service /v1/reports/request
 *
 * Requires an active Auth0 session.
 * Body: { npi: string }
 */

import { getSession } from "@auth0/nextjs-auth0";
import { NextRequest, NextResponse } from "next/server";

const REPORT_SERVICE_URL =
  process.env.REPORT_SERVICE_URL ?? "http://localhost:8004";

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  try {
    const res = await fetch(`${REPORT_SERVICE_URL}/v1/reports/request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15_000),
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
