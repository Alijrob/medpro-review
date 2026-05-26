/**
 * Auth0 universal route handler for Next.js App Router.
 *
 * Handles: /api/auth/login, /api/auth/logout, /api/auth/callback, /api/auth/me
 *
 * Auth0 env vars must be set (see .env.local.example):
 *   AUTH0_SECRET, AUTH0_BASE_URL, AUTH0_ISSUER_BASE_URL,
 *   AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET
 *
 * afterCallback: after a successful login, calls POST /api/auth/sync to link
 * the Auth0 sub to the users row in the payment service DB.  This is
 * best-effort -- a payment service outage must never block login.
 */

import { handleAuth, handleCallback, Session } from "@auth0/nextjs-auth0";

async function syncAfterCallback(
  _req: Request,
  session: Session,
): Promise<Session> {
  // Best-effort: call the internal sync route.  Never throw.
  try {
    const base =
      process.env.NEXT_PUBLIC_APP_URL ??
      process.env.AUTH0_BASE_URL ??
      "http://localhost:3100";

    await fetch(`${base}/api/auth/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Pass session data explicitly since getSession() inside /api/auth/sync
      // may not see the cookie mid-callback.
      body: JSON.stringify({
        email: session.user?.email,
        auth_provider_sub: session.user?.sub,
      }),
      signal: AbortSignal.timeout(5_000),
    });
  } catch (err) {
    console.warn("[auth-callback] afterCallback sync failed (non-fatal):", err);
  }

  return session;
}

export const GET = handleAuth({
  callback: handleCallback({
    afterCallback: syncAfterCallback,
  }),
});
