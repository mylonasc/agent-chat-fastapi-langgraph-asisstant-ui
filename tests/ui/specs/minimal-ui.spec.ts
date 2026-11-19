import { expect, test } from "@playwright/test";
import {
  expectInsideViewport,
  expectNoDuplicateIds,
  expectNoHorizontalOverflow,
  expectVisibleControlsHaveNames,
} from "../lib/dom-quality";

const apiBase = process.env.MINIMAL_API_URL ?? "http://localhost:8011";

test("minimal chat has a stable, accessible DOM", async ({ page }) => {
  const agentRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/agents") {
      agentRequests.push(request.url());
    }
  });
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page).toHaveTitle("assistant-ui Starter App");
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(
    page.getByRole("heading", { level: 1, name: /Start chatting with agent:/ }),
  ).toBeVisible();
  await expect(page.getByRole("main")).toHaveCount(1);
  await expect(page.getByLabel("Message input")).toBeVisible();
  await expect(page.getByText("Ask a question to get started.")).toBeVisible();

  await expectNoHorizontalOverflow(page);
  await expectNoDuplicateIds(page);
  await expectVisibleControlsHaveNames(page);
  await expectInsideViewport(page, ".aui-composer-root");
  await expect.poll(() => agentRequests.length).toBeGreaterThan(0);
  expect(agentRequests.every((url) => url.startsWith(apiBase))).toBe(true);
});

test("minimal chat suggestions and composer adapt to the viewport", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  const suggestions = page.locator(".aui-thread-welcome-suggestion");
  await expect(suggestions).toHaveCount(3);

  const first = await suggestions.nth(0).boundingBox();
  const second = await suggestions.nth(1).boundingBox();
  expect(first).not.toBeNull();
  expect(second).not.toBeNull();

  if (testInfo.project.name.endsWith("mobile")) {
    expect(second!.y).toBeGreaterThan(first!.y);
  }

  const input = page.getByLabel("Message input");
  await input.fill("A DOM-only quality check");
  await expect(
    page.getByRole("button", { name: "Send message" }),
  ).toBeEnabled();
  await expectInsideViewport(page, ".aui-composer-root");
  await expectNoHorizontalOverflow(page);
});
