import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001";

export default defineConfig({
  testDir: "./e2e",
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
