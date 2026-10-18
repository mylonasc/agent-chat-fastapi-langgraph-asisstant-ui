import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001";

export default defineConfig({
  testDir: "./e2e",
  // This legacy app only ships full-backend suites (@full-backend): they
  // need the live compose stack plus credentials, and skip otherwise.
  // Same suites exist under frontend/e2e; see e2e/README.md (#64).
  testMatch: [/(tool-availability|generative-ui-rag)\.spec\.ts/],
  fullyParallel: false,
  timeout: 120_000,
  expect: {
    timeout: 90_000,
  },
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  reporter: [["list"]],
});
