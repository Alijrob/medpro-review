/**
 * Auth0 universal route handler for Next.js App Router.
 *
 * Handles: /api/auth/login, /api/auth/logout, /api/auth/callback, /api/auth/me
 *
 * Auth0 env vars must be set (see .env.local.example):
 *   AUTH0_SECRET, AUTH0_BASE_URL, AUTH0_ISSUER_BASE_URL,
 *   AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET
 */

import { handleAuth } from "@auth0/nextjs-auth0";

export const GET = handleAuth();
