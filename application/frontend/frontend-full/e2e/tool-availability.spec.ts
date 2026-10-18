import { expect, test } from "@playwright/test";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8010";

/** Bearer credential for the fail-closed tool administration APIs (#36).
 * Absent/unauthorized backends answer 503/401 and these specs skip. */
function adminHeaders(): Record<string, string> {
  const token = process.env.FULL_ADMIN_TOKEN;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

test("web_search and web_rag are available from chat UI @full-backend", async ({
  page,
  request,
}) => {
  const overviewRes = await request.get(
    `${API_BASE}/tools/overview?user_id=default_user`,
    { headers: adminHeaders() }
  );
  test.skip(!overviewRes.ok(), "tools overview endpoint is not reachable");

  const overview = await overviewRes.json();
  const runtime = overview?.runtime ?? {};
  test.skip(!runtime.openai_configured, "OPENAI_API_KEY is not configured");
  test.skip(!runtime.serper_configured, "SERPER_API_KEY is not configured");

  await test.step("Prepare RAG index and tool config", async () => {
    const ragConfig = await request.post(`${API_BASE}/tools/web_rag/configuration`, {
      headers: adminHeaders(),
      data: {
        embedding_provider: "fastembed",
      },
    });
    expect(ragConfig.ok()).toBeTruthy();

    const webSearchConfig = await request.post(
      `${API_BASE}/tools/web_search/configuration`,
      {
        headers: adminHeaders(),
        data: { max_results: 3 },
      }
    );
    expect(webSearchConfig.ok()).toBeTruthy();

    const ragIndexResponse = await request.post(`${API_BASE}/tools/web_rag/tools`, {
      headers: adminHeaders(),
      data: {
        action: "index",
        url: "https://example.com",
        user_id: "default_user",
      },
    });
    expect(ragIndexResponse.ok()).toBeTruthy();

    const ragIndexBody = await ragIndexResponse.json();
    expect(["queued", "indexed"]).toContain(ragIndexBody.status);
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
    await expect(page.getByText(/Tool:\s*web_search/i)).toBeVisible();
    await expect(page.getByText(/Tool:\s*web_rag/i)).toBeVisible();
    await expect(page.getByText("TOOLS_OK")).toBeVisible();
  });
});
