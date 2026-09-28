import { expect, test } from "@playwright/test";

const apiBase = process.env.FULL_API_URL ?? "http://localhost:8011";
const enabled = process.env.PERSISTENCE_E2E === "1";

test.skip(!enabled, "requires a local durable backend and Ollama model");

test("completed Ollama turns persist and accept feedback", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();

  const composer = page.getByLabel("Message input");
  await expect(composer).toBeVisible();
  await composer.fill("Reply with exactly: persistence works");
  await composer.press("Enter");

  await expect(page.locator('[data-role="user"]')).toContainText(
    "persistence works",
  );
  // Checkpoint fallback is immediate; wait for the completed-turn transcript
  // synchronizer before asserting durable repository state.
  await page.waitForTimeout(400);
  const readPersisted = async () => page.evaluate(async ({ apiBase }) => {
    const subject = localStorage.getItem("agent-chat.anonymous-subject.v1");
    const headers = subject ? { "x-agent-chat-subject": subject } : {};
    const threads = await fetch(`${apiBase}/threads`, { headers }).then((r) => r.json());
    if (!threads[0]) return { threadId: null, messages: [] };
    const messages = await fetch(`${apiBase}/threads/${threads[0].id}/messages`, {
      headers,
    }).then((r) => r.json());
    return { threadId: threads[0].id, messages: messages.messages };
  }, { apiBase });
  await expect.poll(async () => (await readPersisted()).messages, { timeout: 150_000 }).toHaveLength(2);
  const persisted = await readPersisted();

  const helpful = page.getByRole("button", { name: "Mark response helpful" });
  expect(await page.getByLabel("Message feedback").getAttribute("data-feedback-thread-id")).toBe(
    persisted.threadId,
  );
  const assistantMessageId = await page.locator('[data-role="assistant"]').getAttribute("data-message-id");
  expect(assistantMessageId).toBeTruthy();
  const feedbackPut = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().includes("/feedback") &&
      response.status() === 200,
    { timeout: 15_000 },
  );
  await helpful.click();
  const feedbackResponse = await feedbackPut;
  expect(feedbackResponse.status(), await feedbackResponse.text()).toBe(200);
  await expect(helpful).toHaveAttribute("aria-pressed", "true");

  const readFeedback = async () => page.evaluate(async ({ apiBase, threadId, messageId }) => {
    const subject = localStorage.getItem("agent-chat.anonymous-subject.v1");
    const headers = subject ? { "x-agent-chat-subject": subject } : {};
    if (!threadId) throw new Error("No active thread");
    return fetch(`${apiBase}/threads/${threadId}/messages/${messageId}/feedback`, {
      headers,
    }).then((r) => r.json());
  }, { apiBase, threadId: persisted.threadId, messageId: assistantMessageId });
  await expect.poll(readFeedback).toMatchObject({ rating: "positive" });

});
