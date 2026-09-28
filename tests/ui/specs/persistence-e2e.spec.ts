import { expect, test } from "@playwright/test";

const apiBase = process.env.FULL_API_URL ?? "http://localhost:8011";
const enabled = process.env.PERSISTENCE_E2E === "1";

test.skip(!enabled, "requires a local durable backend and Ollama model");

test("completed Ollama turns survive browser reload", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/");

  const composer = page.getByLabel("Message input");
  await expect(composer).toBeVisible();
  await composer.fill("Reply with exactly: persistence works");
  await composer.press("Enter");

  await expect(page.locator('[data-role="user"]')).toContainText(
    "persistence works",
  );
  const readPersisted = async () => page.evaluate(async ({ apiBase }) => {
    const subject = localStorage.getItem("agent-chat.anonymous-subject.v1");
    const headers = subject ? { "x-agent-chat-subject": subject } : {};
    const threads = await fetch(`${apiBase}/threads`, { headers }).then((r) => r.json());
    if (!threads[0]) return [];
    const messages = await fetch(`${apiBase}/threads/${threads[0].id}/messages`, {
      headers,
    }).then((r) => r.json());
    return messages.messages;
  }, { apiBase });
  await expect.poll(readPersisted, { timeout: 150_000 }).toHaveLength(2);

  await page.reload();
  await expect(page.locator('[data-role="user"]')).toContainText(
    "persistence works",
  );
  await expect(page.locator('[data-role="assistant"]')).toHaveCount(1);
});
