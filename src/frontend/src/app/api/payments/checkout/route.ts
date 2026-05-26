/**
 * Proxy route: POST /api/payments/checkout -> payment service /v1/payments/checkout
 *
 * Requires an active Auth0 session.
 * Client body: { report_id, npi, certified_personal_use_only }
 *
 * This proxy injects success_url and cancel_url server-side so the browser never
 * constructs Stripe redirect URLs, and so they work in any deployment environment
 * without client-side configuration.
 *
 * success_url: /reports/{report_id}?session_id={CHECKOUT_SESSION_ID}
 *   The literal {CHECKOUT_SESSION_ID} is a Stripe template variable -- Stripe
 *   substitutes the real session ID before redirecting the user back.
 *
 * cancel_url: /certify?cancelled=true
 *   Returns the user to the Path B certification page on Stripe abandonment.
 *
 * NEXT_PUBLIC_APP_URL env var overrides the auto-derived host (useful for local dev
 * where the app runs on HTTP, not HTTPS).
 */

import { getSession } from "@auth0/nextjs-auth0";
import { NextRequest, NextResponse } from "next/server";

const PAYMENT_SERVICE_URL =
  process.env.PAYMENT_SERVICE_URL ?? "http://localhost:8005";

function deriveAppBase(req: NextRequest): string {
  // Prefer explicit env var (handles HTTP local dev, custom domains, etc.)
  const override = process.env.NEXT_PUBLIC_APP_URL;
  if (override) return override.replace(/\/$/, "");

  // Fall back to host header (works in production behind TLS termination)
  const host = req.headers.get("host") ?? "localhost:3100";
  const proto = host.startsWith("localhost") ? "http" : "https";
  return `${proto}://${host}`;
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const reportId = body.report_id as string | undefined;
  if (!reportId) {
    return NextResponse.json({ error: "report_id is required" }, { status: 422 });
  }

  const appBase = deriveAppBase(req);

  // Inject Stripe return URLs -- the client never constructs these.
  // {CHECKOUT_SESSION_ID} is a Stripe-native template variable.
  const enrichedBody = {
    ...body,
    success_url: `${appBase}/reports/${reportId}?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${appBase}/certify?cancelled=true`,
    // Pass the Auth0 email so Stripe can pre-fill the checkout form.
    customer_email: session.user?.email ?? undefined,
  };

  try {
    const res = await fetch(`${PAYMENT_SERVICE_URL}/v1/payments/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(enrichedBody),
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
