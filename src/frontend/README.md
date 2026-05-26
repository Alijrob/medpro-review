# medpro-review Frontend (Phase 2-K)

Next.js 14 App Router frontend for `researchyourdoctor.com`.

## Stack

| Layer | Tool |
|-------|------|
| Framework | Next.js 14 (App Router) + TypeScript |
| Auth | `@auth0/nextjs-auth0` v3 |
| Data fetching | TanStack Query v5 |
| Schema validation | Zod |
| Styling | CSS Modules (no external UI lib) |
| Testing | Jest + React Testing Library |

## Architecture

**Browser never calls backend services directly.** All API calls go through
Next.js API Routes (proxy layer) which authenticate the session, then forward
to the appropriate backend service:

```
Browser -> /api/search          -> search service  :8003
Browser -> /api/reports (POST)  -> report service  :8004
Browser -> /api/reports/{id}    -> report service  :8004
Browser -> /api/payments/checkout -> payment service :8005
Browser -> /api/auth/[...auth0] -> Auth0 (Universal Login)
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | Landing page -- sign in CTA |
| `/certify` | Path B personal-use certification (required before search) |
| `/search` | Provider search by name or NPI |
| `/reports/[id]` | Report viewer -- status polling, payment gate, HTML report |

## Auth Flow

1. User clicks "Sign In" -> `/api/auth/login?returnTo=/certify`
2. Auth0 Universal Login
3. Callback -> `/api/auth/callback` -> session cookie set
4. Redirect to `/certify` -- user must certify personal use only
5. On accept: `medpro_path_b_certified` session cookie set -> `/search`
6. Subsequent visits to `/search`/`/reports` check the cert cookie

The legally binding Path B use agreement is written to the database at
payment time (Phase 2-J webhook handler), not at this UI acknowledgment step.

## Report Flow

1. Search for provider
2. Click "Request Report" -> `POST /api/reports` -> report_id returned
3. Navigate to `/reports/{report_id}`
4. `ReportStatusPoller` polls every 3s until status is `complete` or `failed`
5. If `payment_status = "unpaid"`: show `PaymentGate`
6. `PaymentGate` calls `POST /api/payments/checkout` -> Stripe redirect
7. After Stripe checkout: `payment_status = "paid"` -> show `ReportViewer`

## Local Development

```bash
# Copy and fill env vars
cp .env.local.example .env.local
# edit .env.local with Auth0 tenant credentials

# Install dependencies
npm install

# Start dev server (port 3100)
npm run dev
# OR: make run-frontend (from repo root)

# Run tests
npm test
# OR: make frontend-test
```

Backend services need to be running for full functionality:
```bash
make run-search-service   # :8003
make run-report-service   # :8004
make run-payment-service  # :8005
```

## Environment Variables

See `.env.local.example`. All required:

| Variable | Description |
|----------|-------------|
| `AUTH0_SECRET` | 32+ byte random hex (openssl rand -hex 32) |
| `AUTH0_BASE_URL` | App base URL (http://localhost:3100 in dev) |
| `AUTH0_ISSUER_BASE_URL` | Auth0 tenant URL |
| `AUTH0_CLIENT_ID` | Auth0 app client ID |
| `AUTH0_CLIENT_SECRET` | Auth0 app client secret |
| `SEARCH_SERVICE_URL` | Search service URL (default: localhost:8003) |
| `REPORT_SERVICE_URL` | Report service URL (default: localhost:8004) |
| `PAYMENT_SERVICE_URL` | Payment service URL (default: localhost:8005) |

## Non-Deployed (Phase 2-K)

This frontend shell is not yet deployed. Live deployment blocked by:
- DECISIONS.md Entry 003 -- AWS account/region/EKS cluster not provisioned
- Legal gate -- FCRA attorney sign-off pending

Phase 5-A covers full productization (account management, report history, subscriptions).
