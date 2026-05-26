/**
 * Playwright configuration for medpro-review frontend E2E tests.
 *
 * Strategy:
 *   - All backend services + Auth0 are mocked via page.route() -- no live services needed.
 *   - Chromium only in CI (fastest; other browsers are optional locally).
 *   - Global setup project (auth.setup.ts) creates a storageState file with a
 *     mock Auth0 session before any spec runs.
 *   - Base URL is http://localhost:3100 (Next.js dev server or `next start`).
 *
 * See tests/e2e/README.md for run instructions.
 */

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "list" : "html",
  use: {
    baseURL: "http://localhost:3100",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on-first-retry",
  },
  projects: [
    // 1. Auth setup -- runs first, writes playwright/.auth/user.json
    {
      name: "setup",
      testMatch: /setup\/auth\.setup\.ts/,
    },
    // 2. All specs -- depend on auth setup
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
    },
  ],
  // webServer: start Next.js automatically in CI
  // Disabled here so the CI workflow can control the server lifecycle.
});
