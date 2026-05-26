/**
 * auth.setup.ts -- Global auth setup for Playwright E2E tests.
 *
 * Mocks the Auth0 session by intercepting /api/auth/me to return a
 * fixture user object, then saves storageState so authenticated specs
 * get a pre-seeded session without a real Auth0 tenant.
 *
 * Runs before all specs (configured as a Playwright "setup" project).
 * Output: playwright/.auth/user.json (gitignored at runtime; .gitkeep holds the dir)
 */

import { expect, test as setup } from "@playwright/test";
import path from "path";

const AUTH_FILE = path.join(__dirname, "../../playwright/.auth/user.json");

const MOCK_USER = {
  sub: "auth0|test-user-12345",
  name: "Test User",
  email: "testuser@example.com",
  picture: "https://example.com/avatar.png",
};

setup("authenticate", async ({ page }) => {
  // Intercept /api/auth/me to return the mock user.
  await page.route("**/api/auth/me", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_USER),
    });
  });

  // Intercept /api/auth/login to avoid real Auth0 redirect.
  await page.route("**/api/auth/login**", (route) => {
    // Simulate a successful login by redirecting back to the base URL.
    route.fulfill({
      status: 302,
      headers: { Location: "/" },
    });
  });

  // Intercept /api/auth/sync (afterCallback hook) -- just acknowledge.
  await page.route("**/api/auth/sync", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true }),
    });
  });

  // Navigate to the landing page to prime the browser context.
  await page.goto("/");

  // Verify the page loaded (we do not require Auth0 to be configured here).
  await expect(page).toHaveTitle(/Research Your Doctor|medpro/i);

  // Save the browser storage state (cookies + localStorage) for reuse.
  await page.context().storageState({ path: AUTH_FILE });
});
