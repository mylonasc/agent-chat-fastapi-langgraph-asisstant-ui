/** Mid-stream provider-error surfacing per server_mode (stream bomb → quota).
 *
 * Debug config: E2E_PORT=18094 pnpm playwright test -c e2e/provider-error-debug.config.ts
 * Prod config:   E2E_PORT=18093 pnpm playwright test -c e2e/provider-error-prod.config.ts
 *
 * Unlike error-surfacing.spec.ts (factory failure → 503 before streaming),
 * the graph here fails *inside* the stream like an exhausted-credits
 * provider call. The served /api/config decides the assertions, so the
 * same spec runs under both configs.
 */
import { expect, test } from "@playwright/test";

test("mid-stream provider failure renders the red error box per server_mode @packaged", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));
  await page.goto("/");

  const config = await page.request.get("/api/config").then((r) => r.json());
  const debug = config.server_mode === "debug";

  await page.getByLabel("Message input").fill("hello quota");
  await page.getByLabel("Message input").press("Enter");

  const alert = page.locator(".aui-thread-error");
  await expect(alert).toBeVisible({ timeout: 30_000 });
  await expect(alert.locator("[role='alert']")).toBeVisible();

  if (debug) {
    await expect(alert).toContainText("quota_exhausted");
    await expect(alert).toContainText("credits are exhausted");
    await expect(alert).toContainText("billing");
  } else {
    await expect(alert).toContainText("unavailable");
    await expect(alert).not.toContainText("quota_exhausted");
    await expect(alert).not.toContainText("E2E stream bomb");
    await expect(alert).not.toContainText("billing");
  }

  // The app stays alive: no white-screen, composer still enabled.
  expect(pageErrors).toEqual([]);
  await expect(page.getByLabel("Message input")).toBeEnabled();
});
