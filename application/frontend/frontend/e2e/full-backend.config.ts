import { defineConfig } from "@playwright/test";

/**
 * Full-backend e2e gate (#64): specs tagged `@full-backend` assume the live
 * split stack (full backend on :8010 with OPENAI_API_KEY / SERPER_API_KEY,
 * and tool administration credentials via FULL_ADMIN_TOKEN).
 *
 * Without reachable admin-authorized tool APIs these specs skip; they never
 * run against the packaged app. Run:
 *   FULL_ADMIN_TOKEN=... API_BASE_URL=http://localhost:8010 \
 *     pnpm playwright test -c e2e/full-backend.config.ts
 * from `application/frontend/frontend` (or `frontend-full`, same suites).
 */
export default defineConfig({
  testDir: __dirname,
  testMatch: [/(tool-availability|generative-ui-rag)\.spec\.ts/],
  fullyParallel: false,
  workers: 1,
  timeout: 300_000,
  expect: {
    timeout: 90_000,
  },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001",
    trace: "on-first-retry",
  },
  reporter: [["list"]],
});
