import { defineConfig } from "@playwright/test";

/**
 * Pure boundary-validation tests. No browser, no server: these exercise the
 * response normalizers that protect components from malformed backend data.
 */
export default defineConfig({
  testDir: __dirname,
  testMatch: /(api-normalize|assistant-converter|feature-normalize)\.spec\.ts/,
  fullyParallel: true,
  reporter: [["list"]],
});
