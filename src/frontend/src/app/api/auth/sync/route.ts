/**
 * POST /api/auth/sync
 *
 * Server-to-server call triggered by the Auth0 afterCallback hook.
 * Links the Auth0 sub to the users row in the payment service DB.
 *
 * Best-effort: never returns an error to the caller -- a payment service
 * outage must not block Auth0 login.
 *
 * Body: { email: string; auth_provider_sub: string }  (supplied internally)
 * Response: { ok: true }
 */

import { getSession } from "@auth0/nextjs-auth0";
import { NextResponse } from "next/server";

const PAYMENT_SERVICE_URL =
  process.env.PAYMENT_SERVICE_URL ?? "http://localhost:8005";

export async function POST() {
  // Read the Auth0 session -- populated by the time afterCallback fires.
  let session;
  try {
    session = await getSession();
  } catch {
    // Session not available (e.g. called outside an auth context).
    return NextResponse.json({ ok: true, skipped: true });
  }

  if (!session?.user?.email || !session.user.sub) {
    return NextResponse.json({ ok: true, skipped: true, reason: "no_email_or_sub" });
  }

  try {
    await fetch(`${PAYMENT_SERVICE_URL}/v1/users/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: session.user.email,
        auth_provider_sub: session.user.sub,
      }),
      signal: AbortSignal.timeout(5_000),
    });
  } catch (err) {
    // Best-effort: log but never propagate.
    console.warn("[auth-sync] payment service sync failed (non-fatal):", err);
  }

  return NextResponse.json({ ok: true });
}
