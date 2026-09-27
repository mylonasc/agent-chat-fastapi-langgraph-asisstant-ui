import { expect, test } from "@playwright/test";
import path from "node:path";

const turns = [
  { prompt: "Calculate 17 plus 28.", result: "45" },
  { prompt: "Calculate 9 times 7.", result: "63" },
];

function safeName(value: string) {
  return value.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-").replaceAll(/^-|-$/g, "");
}

test.afterEach(async ({ page }, testInfo) => {
  const runId = process.env.E2E_RUN_ID ?? "manual-run";
  const screenshot = path.resolve(
    "screenshots",
    runId,
    `${safeName(testInfo.project.name)}-${safeName(testInfo.title)}.png`,
  );

  await page.screenshot({ path: screenshot, fullPage: true });
  console.log(`Final-state screenshot: ${screenshot}`);
});

test("multi-turn messages remain in chronological order", async ({ page }) => {
  await page.goto("./");

  const input = page.getByLabel("Message input");
  const send = page.getByRole("button", { name: "Send message" });
  await expect(input).toBeVisible();

  for (const [index, turn] of turns.entries()) {
    await input.fill(turn.prompt);
    await send.click();
    await expect(page.locator('[data-role="user"]')).toHaveCount(index + 1);
    await expect(page.locator('[data-role="assistant"]')).toHaveCount(index + 1);
    await expect(page.locator('[data-role="assistant"]').nth(index)).toContainText(turn.result);
    await expect(input).toBeEditable();
  }

  const messages = page.locator('[data-role="user"], [data-role="assistant"]');
  const roles = await messages.evaluateAll((elements) =>
    elements.map((element) => element.getAttribute("data-role")),
  );
  const contents = await messages.evaluateAll((elements) =>
    elements.map((element) => element.textContent?.replaceAll(/\s+/g, " ").trim()),
  );

  console.log("Rendered message roles:", roles);
  console.log("Rendered message contents:", contents);
  expect(roles, "messages must alternate by conversation turn").toEqual([
    "user",
    "assistant",
    "user",
    "assistant",
  ]);
  await expect(page.getByText(/\b2\s*\/\s*2\b/)).toHaveCount(0);
});
