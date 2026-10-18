import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001";

export default defineConfig({
  testDir: "./e2e",
  // Packaged-app default: full-backend suites (@full-backend) need the live
  // compose stack on :8010 plus model/search credentials, so they never run
  // here. Run them explicitly via e2e/full-backend.config.ts (#64).
  testIgnore: [/tool-availability\.spec\.ts/, /generative-ui-rag\.spec\.ts/],
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
