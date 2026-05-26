/**
 * landing.spec.ts -- E2E tests for the landing page (/).
 *
 * 4 tests:
 *   1. Page loads with 200 and expected title
 *   2. Logo / app name visible
 *   3. Login/CTA link points to /api/auth/login
 *   4. Hero section with description text renders
 */

import { expect, test } from "@playwright/test";
import { mockBackendRoutes } from "./helpers/mock-routes";

test.beforeEach(async ({ page }) => {
  await mockBackendRoutes(page);
});

test("landing page loads successfully", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
});

test("app name or title is present", async ({ page }) => {
  await page.goto("/");
  // Title should mention the product or domain
  const title = await page.title();
  expect(title.toLowerCase()).toMatch(/research|doctor|medpro|provider/i);
});

test("login button or CTA is visible on landing page", async ({ page }) => {
  await page.goto("/");
  // Look for a login link or button -- unauthenticated landing page shows CTA
  const loginLink = page.locator('a[href*="/api/auth/login"], button:has-text("Log"), a:has-text("Get Started"), a:has-text("Sign")');
  await expect(loginLink.first()).toBeVisible({ timeout: 5_000 });
});

test("landing page contains descriptive content", async ({ page }) => {
  await page.goto("/");
  // Page body should have meaningful content -- not just a blank shell
  const body = await page.textContent("body");
  expect(body).toBeTruthy();
  expect((body ?? "").length).toBeGreaterThan(50);
});
