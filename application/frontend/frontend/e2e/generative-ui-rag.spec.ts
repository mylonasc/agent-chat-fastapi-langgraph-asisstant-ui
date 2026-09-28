import {
  APIRequestContext,
  expect,
  Locator,
  Page,
  test,
} from "@playwright/test";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8010";

async function getRuntimeFlags(request: APIRequestContext) {
  const overviewRes = await request.get(
    `${API_BASE}/tools/overview?user_id=default_user`
  );
  if (!overviewRes.ok()) return null;
  const overview = await overviewRes.json();
  return overview?.runtime ?? null;
}

async function sendPrompt(page: Page, prompt: string) {
  const composerInput = page.getByLabel("Message input");
  await expect(composerInput).toBeVisible();

  const sendButton = page.getByLabel("Send message");
  if (!(await sendButton.isEnabled())) {
    const newThreadButton = page.getByRole("button", { name: /New Thread/i });
    if (await newThreadButton.isVisible()) {
      await newThreadButton.click();
    }

    if (!(await sendButton.isEnabled())) {
      const existingThreadButton = page
        .getByRole("button", { name: /^New Chat$/ })
        .first();
      if (await existingThreadButton.isVisible()) {
        await existingThreadButton.click();
      }
    }
  }

  await expect(sendButton).toBeEnabled({ timeout: 120_000 });

  await composerInput.fill(prompt);
  await sendButton.click();
}

function widgetForTool(page: Page, toolName: string): Locator {
  return page.getByTestId(`source-indexing-widget-${toolName}`).first();
}

async function openWidget(widget: Locator) {
  const overviewTab = widget.getByRole("button", { name: "Overview" });
  if (!(await overviewTab.isVisible())) {
    await widget.getByTestId(/source-indexing-widget-toggle-/).click();
  }
  await expect(overviewTab).toBeVisible();
}

test("web_search generative widget shows indexing sources and counters", async ({
  page,
  request,
}) => {
  const runtime = await getRuntimeFlags(request);
  test.skip(!runtime, "tools overview endpoint is not reachable");
  test.skip(!runtime.openai_configured, "OPENAI_API_KEY is not configured");
  test.skip(!runtime.serper_configured, "SERPER_API_KEY is not configured");

  await request.post(`${API_BASE}/tools/web_search/configuration`, {
    data: { max_results: 3 },
  });

  await page.goto("/");

  await sendPrompt(
    page,
    [
      "Call web_search exactly once with:",
      "- query: OpenAI",
      "- max_results: 3",
      "- auto_index: true",
      "- wait_for_indexing: true",
      "- rag_urls_to_index: 2",
      "- user_id: default_user",
      "Then respond with exactly SEARCH_INDEX_WIDGET_OK",
    ].join("\n")
  );

  await expect(page.getByText("SEARCH_INDEX_WIDGET_OK")).toBeVisible({
    timeout: 180_000,
  });

  const widget = widgetForTool(page, "web_search");
  await expect(widget).toBeVisible();
  await openWidget(widget);

  await expect(widget.getByText(/indexed docs:/i)).toBeVisible();
  await expect(widget.getByText(/source list origin:/i)).toBeVisible();

  await widget.getByRole("button", { name: /Sources/i }).click();
  await expect(
    widget.getByText("No source entries available for this call.")
  ).toHaveCount(0);
  await expect(widget.getByText(/https?:\/\//i).first()).toBeVisible();
});

test("web_rag generative widget shows retrieved chunks and sources", async ({
  page,
  request,
}) => {
  const runtime = await getRuntimeFlags(request);
  test.skip(!runtime, "tools overview endpoint is not reachable");
  test.skip(!runtime.openai_configured, "OPENAI_API_KEY is not configured");

  const indexRes = await request.post(`${API_BASE}/tools/web_rag/tools`, {
    data: {
      action: "index",
      user_id: "default_user",
      url: "https://example.com",
    },
  });
  expect(indexRes.ok()).toBeTruthy();

  await page.goto("/");

  await sendPrompt(
    page,
    [
      "Call web_rag exactly once with:",
      "- query: example domain",
      "- user_id: default_user",
      "- k: 4",
      "Then respond with exactly RAG_WIDGET_OK",
    ].join("\n")
  );

  await expect(page.getByText("RAG_WIDGET_OK")).toBeVisible({ timeout: 180_000 });

  const widget = widgetForTool(page, "web_rag");
  await expect(widget).toBeVisible();
  await openWidget(widget);

  await widget.getByRole("button", { name: "Retrieval" }).click();
  await expect(
    widget.getByText("No chunks returned in this call (enable as_rag_chunks).")
  ).toHaveCount(0);
  await expect(widget.getByText(/source:/i).first()).toBeVisible();
});
