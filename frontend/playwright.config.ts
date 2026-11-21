// Browser end-to-end tests: a real browser against the running web version.
//
//   docker compose up -d --build --wait      # from the project root
//   npx playwright install chromium          # once
//   npm run e2e
//
// E2E_BASE_URL points them at another address, E2E_USER / E2E_PASSWORD log in
// to a server behind the site password (compose.prod.yaml).
import { defineConfig, devices } from "@playwright/test";

const user = process.env.E2E_USER;
const password = process.env.E2E_PASSWORD;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false, // the tests share one server and its decks
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    httpCredentials: user && password ? { username: user, password } : undefined,
    ignoreHTTPSErrors: !!process.env.E2E_IGNORE_HTTPS_ERRORS, // for a local test certificate
    trace: "retain-on-failure",
  },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"] } },
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
  ],
});
