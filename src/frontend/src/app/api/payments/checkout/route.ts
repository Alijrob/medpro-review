/**
 * Proxy route: POST /api/payments/checkout -> payment service /v1/payments/checkout
 *
 * Requires an active Auth0 session.
 * Body: { report_id, npi, certified_personal_use_only }
 *
 * The response contains checkout_url -- the client redirects the user to Stripe.
 * certified_personal_use_only MUST be true (enforced by the payment service backend).
 */

import { getSession } from "@auth0/nextjs-auth0";
import { NextRequest, NextResponse } from "next/server";

const PAYMENT_SERVICE_URL =
  process.env.PAYMENT_SERVICE_URL ?? "http://localhost:8005";

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
    const res = await fetch(`${PAYMENT_SERVICE_URL}/v1/payments/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[payments-proxy] upstream error:", err);
    return NextResponse.json(
      { error: "Payment service unavailable" },
      { status: 502 },
    );
  }
}
