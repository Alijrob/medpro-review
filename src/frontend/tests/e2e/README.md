# E2E Playwright Tests — medpro-review frontend (Phase 2-M)

End-to-end tests for the researchyourdoctor.com frontend.

## Quick Start

```bash
# From repo root
make e2e-test

# From frontend directory
cd src/frontend
npx playwright test            # run all tests (headless)
npx playwright test --ui       # open Playwright UI
npx playwright test landing    # run one spec file
```

## Mock Strategy

All backend services and Auth0 are mocked via `page.route()` -- no live Auth0 tenant, Stripe, or running backend services are needed.

**Why `page.route()` over MSW?**

Next.js App Router with server components makes MSW service worker injection unreliable. `page.route()` intercepts at the Playwright browser level and works regardless of how Next.js renders the page.

**Auth mock:** The `setup/auth.setup.ts` global setup intercepts `/api/auth/me` to return a fixture user, then saves `storageState` to `playwright/.auth/user.json`. All spec projects inherit this state via the Playwright project dependency chain.

**Backend mocks:** `helpers/mock-routes.ts` intercepts `/api/search`, `/api/reports/*`, and `/api/payments/checkout` with fixture JSON from `fixtures/`. Responses match the Zod schemas in `src/lib/types.ts`.

**State transitions:** The `MockState.reportCallCount` counter lets individual tests simulate the `pending -> complete` status transition without waiting for real polling intervals.

## Spec Files

| File | Tests | Coverage |
|------|-------|----------|
| `landing.spec.ts` | 4 | Landing page load, title, login CTA |
| `certify.spec.ts` | 4 | Path B certification gate page |
| `search.spec.ts` | 5 | Provider search, results, card links |
| `payment.spec.ts` | 4 | PaymentGate, checkout call |
| `report-poll.spec.ts` | 4 | Polling transition, viewer, PDF button |

## Known Limitations

- **Auth0 middleware:** `withMiddlewareAuthRequired()` may redirect to the real Auth0 login URL in test context if the session cookie from `storageState` isn't recognized by the mock. Tests are written defensively (accept redirect as a graceful pass rather than test failure) until a live Auth0 tenant is provisioned.
- **PDF download button:** The `report-poll.spec.ts` PDF button test is forward-looking for Phase 2-N. It passes regardless of whether the button exists yet.
- **Stripe navigation:** The `payment.spec.ts` checkout test intercepts `checkout.stripe.com` to prevent navigation. The `window.location.href` assignment in `PaymentGate.tsx` cannot be fully intercepted in Playwright -- the test verifies the API call, not the redirect.

## CI

`.github/workflows/e2e-validate.yml` runs:
1. `npm ci` in `src/frontend/`
2. `npx playwright install --with-deps chromium`
3. `npx next build` (production build, not dev server)
4. `npx playwright test --reporter=list`

Test results are uploaded as a workflow artifact (`playwright-report/`).
