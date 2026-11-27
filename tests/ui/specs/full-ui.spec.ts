import { expect, test } from "@playwright/test";
import {
  expectInsideViewport,
  expectNoDuplicateIds,
  expectNoHorizontalOverflow,
  expectNoElementOverflow,
  expectVisibleControlsHaveNames,
} from "../lib/dom-quality";
import {
  mockStreamingTurn,
  mockTurnDetails,
  storedMessage,
  toolPart,
} from "../lib/turn-details-fixture";
import { mockTooling } from "../lib/tooling-fixture";

const apiBase = process.env.FULL_API_URL ?? "http://localhost:8010";

test.beforeEach(async ({ page }) => {
  await page.route(`${apiBase}/**`, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/config") {
      await route.fulfill({
        json: {
          version: 1, api_base: apiBase, ui_preset: "full",
          features: { assistant: true, agents: false, threads: true, transcripts: true },
          tooling: { enabled: false, tool_names: [] },
          presentation: {
            welcome_description:
              "Ask a question or search and index web sources.",
          },
        },
      });
      return;
    }
    if (url.pathname === "/threads" && route.request().method() === "GET") {
      await route.fulfill({ json: [] });
      return;
    }
    if (url.pathname.endsWith("/messages")) {
      await route.fulfill({ json: { messages: [] } });
      return;
    }
    if (url.pathname === "/tools/web_rag/status") {
      await route.fulfill({
        json: { index: { source_count: 0, document_count: 0 }, jobs: [] },
      });
      return;
    }
    await route.fulfill({ json: {} });
  });
});

test("full chat has a stable, accessible DOM", async ({ page }) => {
  const unavailableCapabilityRequests: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path === "/agents" || path === "/tools/web_rag/status") {
      unavailableCapabilityRequests.push(path);
    }
  });
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page).toHaveTitle("assistant-ui Starter App");
  await expect(page.getByRole("main")).toHaveCount(1);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Start chatting with agent: default",
    }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByLabel("Message input")).toBeVisible();
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Add Attachment" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Ask a question or search and index web sources."),
  ).toBeVisible();

  await expectNoHorizontalOverflow(page);
  await expectNoDuplicateIds(page);
  await expectVisibleControlsHaveNames(page);
  await expectInsideViewport(page, ".aui-composer-root");
  await page.waitForTimeout(1500);
  expect(unavailableCapabilityRequests).toEqual([]);
});

test("full chat responsive navigation remains operable", async ({
  page,
}, testInfo) => {
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

test("turn tools render only in the right details panel", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await mockTurnDetails(page, apiBase);
  await page.goto("/");

  const responses = page.locator('[data-role="assistant"]');
  await expect(responses).toHaveCount(3);
  await expect(responses.first()).toContainText("First answer");
  await expect(responses.locator(".aui-tool-fallback-root")).toHaveCount(0);
  await expect(
    responses.getByTestId("source-indexing-widget-web_search"),
  ).toHaveCount(0);
  await expect(page.getByTestId("turn-details-sidebar")).toHaveCount(0);

  const show = responses
    .first()
    .getByRole("button", { name: "Show details", includeHidden: true });
  await show.press("Enter");
  await expect(show).toHaveAttribute("aria-expanded", "true");
  const panel = page.getByTestId("turn-details-sidebar");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("2 tool calls");
  await expect(panel).toContainText("input-for-calculator");
  await expect(panel).toContainText('"answer": 42');
  await expect(panel).not.toContainText("second-result");
  await expect(panel).not.toContainText("First answer");

  // Registered RAG renderers retain their interactive controls in the sidebar.
  const widget = panel.getByTestId("source-indexing-widget-web_search");
  await expect(widget).toBeVisible();
  await widget.getByTestId("source-indexing-widget-toggle-web_search").click();
  await expect(
    widget.getByRole("button", { name: "Overview", exact: true }),
  ).toBeVisible();
  await expectNoElementOverflow(
    page,
    '[data-testid="source-indexing-widget-web_search"]',
  );
  await widget.getByRole("button", { name: /Sources/ }).click();
  await expect(
    widget.getByText("https://example.com", { exact: true }),
  ).toBeVisible();

  await expectInsideViewport(page, '[data-testid="turn-details-sidebar"]');
  await expectNoElementOverflow(
    page,
    ".aui-tool-fallback-args-value, .aui-tool-fallback-result-content",
  );
  await expectNoHorizontalOverflow(page);
  await expectNoDuplicateIds(page);
  await expectVisibleControlsHaveNames(page);
  if (testInfo.project.name.endsWith("mobile")) {
    await expect(panel).toHaveAttribute("role", "dialog");
  } else {
    await expect(panel).toHaveAttribute("aria-labelledby", /title$/);
    const chatBox = await page.locator(".aui-thread-viewport").boundingBox();
    const panelBox = await panel.boundingBox();
    expect(panelBox!.x).toBeGreaterThanOrEqual(chatBox!.x + chatBox!.width - 1);
    await expect(page.getByLabel("Message input")).toBeEnabled();
    await expectInsideViewport(page, ".aui-composer-root");
    await page.setViewportSize({ width: 900, height: 900 });
    await expectInsideViewport(page, '[data-testid="turn-details-sidebar"]');
    await expectNoElementOverflow(
      page,
      '[data-testid="source-indexing-widget-web_search"]',
    );
    await expectNoHorizontalOverflow(page);
  }

  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
  await expect(show).toBeFocused();
  await expect(show).toHaveAttribute("aria-expanded", "false");
  expect(errors).toEqual([]);
});

test("details remain scoped to each turn and can be closed and reopened", async ({
  page,
}) => {
  await mockTurnDetails(page, apiBase);
  await page.goto("/");
  const responses = page.locator('[data-role="assistant"]');
  await expect(responses).toHaveCount(3);
  const panel = page.getByTestId("turn-details-sidebar");
  const second = responses.nth(1).getByRole("button", { name: "Show details" });
  await second.click();
  await expect(panel).toContainText("second-result");
  await expect(panel).not.toContainText("calculator");
  await panel.getByRole("button", { name: /^Close/ }).click();
  await expect(panel).toHaveCount(0);
  await expect(second).toBeFocused();
  await second.click();
  await expect(panel).toContainText("second-result");
  await page.keyboard.press("Escape");

  await responses.nth(2).getByRole("button", { name: "Show details" }).click();
  await expect(panel).toContainText("No tool calls were made in this turn.");
  await expect(panel.locator(".aui-tool-fallback-root")).toHaveCount(0);
  await page.keyboard.press("Escape");

  // Hydration keeps tools available but does not force the panel open.
  await page.reload();
  await expect(responses).toHaveCount(3);
  await expect(panel).toHaveCount(0);
  await responses.first().getByRole("button", { name: "Show details" }).click();
  await expect(panel).toContainText('"answer": 42');
});

test("branch and thread changes never show another response's tools", async ({
  page,
}, testInfo) => {
  await mockTurnDetails(page, apiBase, [
    storedMessage("prompt", "user", [
      { type: "text", text: "Branched question" },
    ]),
    storedMessage(
      "original",
      "assistant",
      [
        toolPart("original_tool", { answer: "original-result" }),
        { type: "text", text: "Original answer" },
      ],
      "prompt",
    ),
    storedMessage(
      "alternative",
      "assistant",
      [
        toolPart("alternative_tool", { answer: "alternative-result" }),
        { type: "text", text: "Alternative answer" },
      ],
      "prompt",
    ),
  ]);
  await page.goto("/");
  const response = page.locator('[data-role="assistant"]');
  await expect(response).toContainText("Alternative answer");
  const panel = page.getByTestId("turn-details-sidebar");
  await response.getByRole("button", { name: "Show details" }).click();
  await expect(panel).toContainText("alternative-result");
  // Dismiss the mobile modal before interacting with the branch picker.
  if (testInfo.project.name.endsWith("mobile"))
    await page.keyboard.press("Escape");
  await response.getByRole("button", { name: "Previous", exact: true }).click();
  await expect(panel).toHaveCount(0);
  await response.getByRole("button", { name: "Show details" }).click();
  await expect(panel).toContainText("original-result");
  await expect(panel).not.toContainText("alternative-result");
  if (testInfo.project.name.endsWith("mobile")) {
    await page.keyboard.press("Escape");
    await page.locator('[data-slot="sidebar-trigger"]').click();
  }
  await page.getByRole("button", { name: "New Thread", exact: true }).click();
  await expect(response).toHaveCount(0);
  await expect(panel).toHaveCount(0);
});

test("an open details panel updates as tool results stream in", async ({
  page,
}) => {
  const stream = await mockStreamingTurn(page);
  try {
    await page.goto("/");
    const input = page.getByLabel("Message input");
    await expect(input).toBeEnabled();
    await input.fill("Stream a tool");
    await input.press("Enter");
    const response = page.locator('[data-role="assistant"]');
    await expect(response).toContainText("Checking the tool.");
    await expect(response.locator(".aui-tool-fallback-root")).toHaveCount(0);
    await response.getByRole("button", { name: "Show details" }).click();
    const panel = page.getByTestId("turn-details-sidebar");
    await expect(panel).toContainText("slow_tool");
    await expect(panel).toContainText("Running");
    await expect(panel).toContainText("stream-input");

    stream.complete();
    await expect(panel).toContainText("streamed-result");
    await expect(panel).toContainText("Completed");
    await expect(panel).not.toContainText("Running");
    await expect(response).toContainText("Finished streaming answer");
    await expect(response).not.toContainText("streamed-result");
    await expect(panel).toContainText("1 tool call");
    await page.keyboard.press("Escape");
    await expect(input).toBeEnabled();
    await expectNoHorizontalOverflow(page);
  } finally {
    await stream.close();
  }
});

test("administrators manage toolsets and schema-driven knobs without storing credentials", async ({
  page,
}) => {
  const fixture = await mockTooling(page, apiBase);
  await page.goto("/toolsets");
  await expect(
    page.getByRole("heading", { name: "Toolsets and tools" }),
  ).toBeVisible();
  await expect(page.getByLabel("Enable Calculator toolset")).toBeDisabled();
  await page
    .getByLabel("Administrator token", { exact: false })
    .fill("wrong-token");
  await page.getByRole("button", { name: "Unlock administration" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Administrator authorization required",
  );
  await page
    .getByLabel("Administrator token", { exact: false })
    .fill("admin-demo");
  await page.getByRole("button", { name: "Unlock administration" }).click();
  await expect(page.getByLabel("Enable Calculator toolset")).toBeEnabled();
  await page.getByLabel("Enable Demo weather toolset").uncheck();
  await page.getByLabel("Divide: Decimal places").fill("2");
  await page.getByLabel("Enable Web RAG toolset").check();
  await expect(
    page.getByLabel("Retrieve documents: Embedding provider"),
  ).toBeDisabled();
  await page
    .getByLabel("Retrieve documents: Bootstrap an empty index from the web")
    .check();
  await page.getByRole("button", { name: "Save tool settings" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Application tool settings saved",
  );
  expect(fixture.writes).toHaveLength(1);
  expect(fixture.writes[0].body.toolsets).toEqual(["calculator", "web_rag"]);
  expect(fixture.writes[0].body.tools.divide.config.precision).toBe(2);
  expect(fixture.writes[0].body.tools.web_rag.config).not.toHaveProperty(
    "embedding_provider",
  );
  expect(JSON.stringify(fixture.writes[0].body)).not.toContain("admin-demo");
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    ),
  ).not.toContain("admin-demo");
  await expectNoHorizontalOverflow(page);
  await expectNoDuplicateIds(page);
  await expectVisibleControlsHaveNames(page);
  await page.reload();
  await expect(
    page.getByLabel("Administrator token", { exact: false }),
  ).toHaveValue("");
  await expect(
    page.getByLabel("Enable Demo weather toolset"),
  ).not.toBeChecked();
  await expect(page.getByLabel("Divide: Decimal places")).toHaveValue("2");
  await expect(page.getByLabel("Enable Calculator toolset")).toBeDisabled();
});

for (const preset of ["minimal", "full"] as const) {
  test(`${preset} UI supports durable per-conversation tool choices and stale-edit recovery`, async ({
    page,
  }) => {
    const fixture = await mockTooling(page, apiBase, preset);
    await page.goto("/");
    const trigger = page.getByRole("button", {
      name: "Conversation tools",
      exact: true,
    });
    await expect(trigger).toBeEnabled();
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "Conversation tools" });
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("Enable Demo weather toolset").uncheck();
    await dialog.getByLabel("Divide: Decimal places").fill("3");
    await expect(dialog.getByLabel("Enable Web RAG toolset")).toBeDisabled();
    await dialog.getByRole("button", { name: "Save tool settings" }).click();
    await expect(dialog.getByRole("status")).toContainText(
      "Tool settings saved",
    );
    expect(fixture.writes[0].authorization).toBeUndefined();
    expect(fixture.writes[0].body.toolsets).toEqual(["calculator"]);
    await page.keyboard.press("Escape");
    await page.reload();
    await trigger.click();
    await expect(
      dialog.getByLabel("Enable Demo weather toolset"),
    ).not.toBeChecked();
    await expect(dialog.getByLabel("Divide: Decimal places")).toHaveValue("3");
    fixture.disableGlobally();
    await dialog.getByRole("button", { name: "Save tool settings" }).click();
    await expect(dialog.getByRole("alert")).toContainText(
      "Refresh before saving",
    );
    await dialog.getByRole("button", { name: "Refresh settings" }).click();
    await expect(dialog.getByLabel("Enable Calculator toolset")).toBeDisabled();
    await expectInsideViewport(page, '[role="dialog"]');
    await expectNoHorizontalOverflow(page);
    await expectNoDuplicateIds(page);
    await expectVisibleControlsHaveNames(page);
    await page.keyboard.press("Escape");
    await expect(page.getByLabel("Message input")).toBeEnabled();
  });
}
