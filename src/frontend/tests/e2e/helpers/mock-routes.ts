/**
 * mock-routes.ts -- Shared page.route() helpers for E2E specs.
 *
 * All backend API routes are intercepted here so specs run without live services.
 * Fixture JSON files in tests/e2e/fixtures/ provide realistic response shapes
 * that match the Zod schemas in src/lib/types.ts.
 */

import { Page } from "@playwright/test";
import searchResults from "../fixtures/search-results.json";
import reportPending from "../fixtures/report-pending.json";
import reportComplete from "../fixtures/report-complete.json";
import checkoutResponse from "../fixtures/checkout-response.json";

/** Call count tracker per spec -- lets tests simulate state transitions. */
export interface MockState {
  reportCallCount: number;
}

/**
 * Install mock routes on a page.  Call this at the top of each spec's
 * beforeEach or test body.
 *
 * @param page   Playwright Page
 * @param state  Shared state object -- increment reportCallCount to trigger
 *               the pending->complete transition in report polling tests.
 */
export async function mockBackendRoutes(
  page: Page,
  state: MockState = { reportCallCount: 0 },
): Promise<void> {
  // Auth0 me endpoint
  await page.route("**/api/auth/me", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        sub: "auth0|test-user-12345",
        name: "Test User",
        email: "testuser@example.com",
        picture: "https://example.com/avatar.png",
      }),
    });
  });

  // Auth sync (afterCallback)
  await page.route("**/api/auth/sync", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true }),
    });
  });

  // Provider search
  await page.route("**/api/search**", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(searchResults),
    });
  });

  // Request a new report (POST /api/reports)
  await page.route(
    (url) => url.pathname === "/api/reports" && url.href.includes("api/reports"),
    (route) => {
      if (route.request().method() === "POST") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            report_id: reportPending.report_id,
            status: "pending",
            db_persisted: false,
            temporal_queued: false,
          }),
        });
      } else {
        route.continue();
      }
    },
  );

  // Get report status (GET /api/reports/{id}) -- transitions pending->complete
  await page.route("**/api/reports/**", (route) => {
    if (route.request().method() === "GET") {
      state.reportCallCount++;
      const fixture = state.reportCallCount >= 2 ? reportComplete : reportPending;
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(fixture),
      });
    } else {
      route.continue();
    }
  });

  // Stripe checkout (POST /api/payments/checkout)
  await page.route("**/api/payments/checkout", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(checkoutResponse),
    });
  });
}
