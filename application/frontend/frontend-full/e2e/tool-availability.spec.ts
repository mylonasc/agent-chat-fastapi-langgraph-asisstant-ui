import { expect, test } from "@playwright/test";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8010";

test("web_search and web_rag are available from chat UI", async ({
  page,
  request,
}) => {
  await test.step("Prepare RAG index and tool config", async () => {
    const ragConfig = await request.post(`${API_BASE}/tools/web_rag/configuration`, {
      data: {
        embedding_provider: "fastembed",
      },
    });
    expect(ragConfig.ok()).toBeTruthy();

    const webSearchConfig = await request.post(
      `${API_BASE}/tools/web_search/configuration`,
      {
        data: { max_results: 3 },
      }
    );
    expect(webSearchConfig.ok()).toBeTruthy();

    const ragIndexResponse = await request.post(`${API_BASE}/tools/web_rag/tools`, {
      data: {
        action: "index",
        url: "https://example.com",
        user_id: "default_user",
      },
    });
    expect(ragIndexResponse.ok()).toBeTruthy();

    const ragIndexBody = await ragIndexResponse.json();
    expect(ragIndexBody.status).toBe("indexed");
  });

  await test.step("Send message that requires both tools", async () => {
    await page.goto("/");

    const composerInput = page.getByLabel("Message input");
    await expect(composerInput).toBeVisible();

    const sendButton = page.getByLabel("Send message");
    await expect(sendButton).toBeEnabled();

    await composerInput.fill(
      [
        "For verification, you must use both tools exactly once:",
        "1) Call web_search with query 'OpenAI'.",
        "2) Call web_rag with query 'example domain'.",
        "Then answer with exactly: TOOLS_OK",
      ].join("\n")
    );
    await sendButton.click();
  });

  await test.step("Verify tool calls appear in UI", async () => {
    await expect(page.getByText("Used tool: web_search")).toBeVisible();
    await expect(page.getByText("Used tool: web_rag")).toBeVisible();
    await expect(page.getByText("TOOLS_OK")).toBeVisible();
  });
});
