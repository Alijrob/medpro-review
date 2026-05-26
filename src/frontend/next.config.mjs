/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // All backend service URLs are proxied via /api/* API routes.
  // These env vars are server-only (no NEXT_PUBLIC_ prefix) so they never
  // reach the browser bundle.
  //
  // Defaults point to local dev ports; override via environment in production.
  //   SEARCH_SERVICE_URL  -> search service  (:8003)
  //   REPORT_SERVICE_URL  -> report service  (:8004)
  //   PAYMENT_SERVICE_URL -> payment service (:8005)

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
        ],
      },
    ];
  },
};

export default nextConfig;
