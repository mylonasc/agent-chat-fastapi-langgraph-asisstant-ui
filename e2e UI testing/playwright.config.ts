import { defineConfig } from "@playwright/test";

const fullUiUrl = process.env.FULL_UI_URL ?? "http://127.0.0.1:8011/";
const minimalUiUrl = process.env.MINIMAL_UI_URL ?? "http://127.0.0.1:8012/";

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 90_000 },
  reporter: [["list"]],
  use: {
    trace: "retain-on-failure",
    video: "off",
    viewport: { width: 1440, height: 1000 },
  },
  projects: [
    {
      name: "full-ui",
      use: { baseURL: fullUiUrl },
    },
    {
      name: "minimal-ui",
      use: { baseURL: minimalUiUrl },
    },
  ],
});
