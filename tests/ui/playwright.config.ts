import { defineConfig, devices } from "@playwright/test";

const fullBaseURL = process.env.FULL_UI_URL ?? "http://localhost:3001";
const minimalBaseURL = process.env.MINIMAL_UI_URL ?? "http://localhost:3000";
const selectedStack = process.env.PLAYWRIGHT_STACK;

const webServer = [
  selectedStack !== "minimal"
    ? {
        command: "docker compose -f ../../docker-compose.full.yml up --build",
        url: fullBaseURL,
        reuseExistingServer: true,
        timeout: 180_000,
        gracefulShutdown: { signal: "SIGTERM" as const, timeout: 10_000 },
      }
    : null,
  selectedStack !== "full"
    ? {
        command: "docker compose -f ../../docker-compose.minimal.yml up --build",
        url: minimalBaseURL,
        reuseExistingServer: true,
        timeout: 180_000,
        gracefulShutdown: { signal: "SIGTERM" as const, timeout: 10_000 },
      }
    : null,
].filter((server): server is NonNullable<typeof server> => server !== null);

export default defineConfig({
  testDir: "./specs",
  outputDir: "./test-results",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    screenshot: "off",
    trace: "off",
    video: "off",
  },
  webServer,
  projects: [
    {
      name: "full-desktop",
      testMatch: /full-ui\.spec\.ts/,
      use: { baseURL: fullBaseURL, viewport: { width: 1440, height: 900 } },
    },
    {
      name: "full-mobile",
      testMatch: /full-ui\.spec\.ts/,
      use: { ...devices["Pixel 7"], baseURL: fullBaseURL },
    },
    {
      name: "minimal-desktop",
      testMatch: /minimal-ui\.spec\.ts/,
      use: { baseURL: minimalBaseURL, viewport: { width: 1440, height: 900 } },
    },
    {
      name: "minimal-mobile",
      testMatch: /minimal-ui\.spec\.ts/,
      use: { ...devices["Pixel 7"], baseURL: minimalBaseURL },
    },
  ],
});
