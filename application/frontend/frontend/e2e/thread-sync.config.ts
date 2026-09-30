import { defineConfig } from "@playwright/test";
import path from "node:path";

const port = Number(process.env.E2E_PORT ?? "18099");

export default defineConfig({
  testDir: __dirname,
  testMatch: /thread-sync\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: {
    timeout: 30_000,
  },
  use: {
    baseURL: `http://localhost:${port}`,
    trace: "on-first-retry",
  },
  webServer: {
    command: `${process.env.E2E_PYTHON ?? "python3"} ${path.join(__dirname, "helpers", "fake_backend.py")}`,
    cwd: path.join(__dirname, ".."),
    url: `http://localhost:${port}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      E2E_PORT: String(port),
    },
  },
  reporter: [["list"]],
});
