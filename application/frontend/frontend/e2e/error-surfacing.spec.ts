/** Backend-error surfacing per server_mode (bomb factory → 503 on send).
 *
 * Debug config: E2E_PORT=18096 pnpm playwright test -c e2e/error-debug.config.ts
 * Prod config:   E2E_PORT=18095 pnpm playwright test -c e2e/error-prod.config.ts
 *
 * The served /api/config decides the assertions, so the same spec runs
 * under both configs.
 */
import { expect, test } from "@playwright/test";

test("failed send surfaces the backend error according to server_mode", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));
  await page.goto("/");

  const config = await page.request.get("/api/config").then((r) => r.json());
  const debug = config.server_mode === "debug";

  await page.getByLabel("Message input").fill("hello bomb");
  await page.getByLabel("Message input").press("Enter");

  const alert = page.locator(".aui-thread-error");
  await expect(alert).toBeVisible({ timeout: 30_000 });
  await expect(alert.locator("[role='alert']")).toBeVisible();

  if (debug) {
    await expect(alert).toContainText("Request failed (503)");
    await expect(alert).toContainText("agent_not_ready");
    await expect(alert).toContainText("E2E bomb");
    await expect(alert).toContainText("pip install langchain-ollama");
  } else {
    await expect(alert).toContainText("unavailable");
    await expect(alert).not.toContainText("E2E bomb");
    await expect(alert).not.toContainText("pip install");
    await expect(alert).not.toContainText("503");
  }

  // The app stays alive: no white-screen, composer still enabled.
  expect(pageErrors).toEqual([]);
  await expect(page.getByLabel("Message input")).toBeEnabled();
});
