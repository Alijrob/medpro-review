/**
 * Next.js middleware -- Auth0 session gate.
 *
 * Routes under /search and /reports require an authenticated Auth0 session.
 * withMiddlewareAuthRequired redirects unauthenticated users to /api/auth/login.
 *
 * Path B certification is checked at the page level (cookie medpro_path_b_certified)
 * so the certification page itself (/certify) is also protected.
 */

import { withMiddlewareAuthRequired } from "@auth0/nextjs-auth0/edge";

export default withMiddlewareAuthRequired();

export const config = {
  matcher: ["/search/:path*", "/reports/:path*", "/certify/:path*"],
};
