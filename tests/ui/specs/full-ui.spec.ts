import { expect, test } from "@playwright/test";
import {
  expectInsideViewport,
  expectNoDuplicateIds,
  expectNoHorizontalOverflow,
  expectVisibleControlsHaveNames,
} from "../lib/dom-quality";

const apiBase = process.env.FULL_API_URL ?? "http://localhost:8010";

test.beforeEach(async ({ page }) => {
  await page.route(`${apiBase}/**`, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/threads" && route.request().method() === "GET") {
      await route.fulfill({ json: [] });
      return;
    }
    if (url.pathname.endsWith("/messages")) {
      await route.fulfill({ json: { messages: [] } });
      return;
    }
    if (url.pathname === "/tools/web_rag/status") {
      await route.fulfill({ json: { index: { source_count: 0, document_count: 0 }, jobs: [] } });
      return;
    }
    await route.fulfill({ json: {} });
  });
});

test("full chat has a stable, accessible DOM", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page).toHaveTitle("assistant-ui Starter App");
  await expect(page.getByRole("main")).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 1, name: "Hello there!" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByLabel("Message input")).toBeVisible();
  await expect(page.getByRole("link", { name: "Admin" })).toBeVisible();
  await expect(page.getByText("Hello there!", { exact: true })).toBeVisible();

  await expectNoHorizontalOverflow(page);
  await expectNoDuplicateIds(page);
  await expectVisibleControlsHaveNames(page);
  await expectInsideViewport(page, ".aui-composer-root");
});

test("full chat responsive navigation remains operable", async ({ page }, testInfo) => {
  await page.goto("/");
  const trigger = page.locator('[data-slot="sidebar-trigger"]');
  await expect(trigger).toBeVisible();

  if (testInfo.project.name.endsWith("mobile")) {
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "Sidebar" });
    await expect(dialog).toBeVisible();
    await expectInsideViewport(page, '[role="dialog"]');
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  } else {
    const sidebar = page.locator('[data-slot="sidebar"]');
    await expect(sidebar).toHaveAttribute("data-state", "expanded");
    await trigger.click();
    await expect(sidebar).toHaveAttribute("data-state", "collapsed");
  }

  await expectNoHorizontalOverflow(page);
});
