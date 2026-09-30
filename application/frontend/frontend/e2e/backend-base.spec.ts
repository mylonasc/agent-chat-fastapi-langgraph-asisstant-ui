/** Backend-base + thread-lifecycle regression suite (same-origin deployment).
 *
 * Covers three user-reported defects and their root cause:
 *  1. Pre-config backend I/O went to the build-time fallback base
 *     (http://localhost:8010) instead of the deployment backend, poisoning
 *     hydration/sync with a foreign server. No request may target it.
 *  2. Chat titles only updated on the second exchange; they must update
 *     when the first response arrives.
 *  3. Archiving left threads visible; archived threads must leave the
 *     list and stay gone across reloads.
 *  4. Fresh threads (launch, New Thread, post-archive landing) show the
 *     starter page, visually distinct from an empty chat.
 *
 * Run: E2E_PORT=18097 pnpm playwright test -c e2e/backend-base.config.ts
 */
import { expect, test, type Page } from "@playwright/test";

/** Abort anything aimed at the build-time fallback base and count attempts. */
async function guardFallbackBase(page: Page): Promise<{ count: () => number }> {
  let count = 0;
  await page.route("http://localhost:8010/**", (route) => {
    count += 1;
    void route.abort();
  });
  return { count: () => count };
}

async function sendMessage(page: Page, text: string) {
  await page.getByLabel("Message input").fill(text);
  await page.getByLabel("Message input").press("Enter");
}

async function waitForAssistantReply(page: Page, text: string) {
  await expect
    .poll(
      async () => page.locator('[data-role="assistant"]').getByText(text).count(),
      { timeout: 30_000 },
    )
    .toBeGreaterThan(0);
}

async function sidebarTitles(page: Page): Promise<string[]> {
  return page.locator(".aui-thread-list-item-title").allInnerTexts();
}

async function apiHeaders(page: Page): Promise<Record<string, string>> {
  const subject = await page.evaluate(() =>
    window.localStorage.getItem("agent-chat.anonymous-subject.v1"),
  );
  return { "x-agent-chat-subject": String(subject) };
}

test("all backend I/O targets the deployment backend, never the fallback base", async ({
  page,
}) => {
  const guard = await guardFallbackBase(page);
  const bad: string[] = [];
  page.on("response", (r) => {
    if (r.status() >= 400 && !r.url().includes("/feedback")) {
      bad.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    }
  });
  await page.goto("/");
  await sendMessage(page, "fallback guard turn one");
  await waitForAssistantReply(page, "reply-1");
  await sendMessage(page, "fallback guard turn two");
  await waitForAssistantReply(page, "reply-2");
  await page.waitForTimeout(1500);
  await page.reload();
  await page.waitForTimeout(2500);
  expect(await sidebarTitles(page)).toHaveLength(1);
  expect(guard.count()).toBe(0);
  expect(bad).toEqual([]);
});

test("chat title updates when the first response arrives", async ({ page }) => {
  await guardFallbackBase(page);
  await page.goto("/");
  await expect(page.locator(".aui-starter-page")).toBeVisible();
  await sendMessage(page, "hexagonal architecture principles");
  await waitForAssistantReply(page, "reply-1");
  await expect
    .poll(async () => page.getByTitle("Rename chat").innerText(), {
      timeout: 30_000,
    })
    .toBe("hexagonal architecture principles");
  expect(await sidebarTitles(page)).toEqual([
    "hexagonal architecture principles",
  ]);
});

test("archiving removes the thread from the list, permanently", async ({
  page,
}) => {
  await guardFallbackBase(page);
  await page.goto("/");
  await sendMessage(page, "thread alpha content");
  await waitForAssistantReply(page, "reply-1");
  await page.waitForTimeout(1200);
  const headers = await apiHeaders(page);
  const listA = await page.request
    .get("/threads", { headers })
    .then((r) => r.json());
  const idA: string = listA[0].id;
  await page.request.patch(`/threads/${idA}`, {
    headers,
    data: { title: "Thread ALPHA" },
  });
  await page.getByRole("button", { name: "New Thread" }).click();
  await expect(page.locator(".aui-starter-page")).toBeVisible();
  await sendMessage(page, "thread beta content");
  await waitForAssistantReply(page, "reply-1");
  await page.waitForTimeout(1200);
  const listB = await page.request
    .get("/threads", { headers })
    .then((r) => r.json());
  const idB: string = listB.find((t: any) => t.id !== idA).id;
  await page.request.patch(`/threads/${idB}`, {
    headers,
    data: { title: "Thread BETA" },
  });
  await page.reload();
  await page.waitForTimeout(2000);
  expect(await sidebarTitles(page)).toEqual(["Thread BETA", "Thread ALPHA"]);

  // Archive the active thread: it leaves the list and lands on the starter.
  await page
    .locator(".aui-thread-list-item", { hasText: "Thread BETA" })
    .getByRole("button", { name: "Archive thread" })
    .click();
  await expect
    .poll(sidebarTitles.bind(null, page), { timeout: 30_000 })
    .toEqual(["Thread ALPHA"]);
  const serverActive = await page.request
    .get("/threads", { headers })
    .then((r) => r.json());
  expect(serverActive.map((t: any) => t.title)).toEqual(["Thread ALPHA"]);
  const serverAll = await page.request
    .get("/threads?include_archived=true", { headers })
    .then((r) => r.json());
  expect(
    serverAll.find((t: any) => t.id === idB).is_archived,
  ).toBe(true);
  await expect(page.locator(".aui-starter-page")).toBeVisible();

  await page.reload();
  await page.waitForTimeout(2000);
  // The archived thread stays gone; the only other row is the empty landing
  // thread the runtime bound after the archive (a fresh "New Chat").
  expect(await sidebarTitles(page)).toEqual(["New Chat", "Thread ALPHA"]);
});

test("starter page names the agent and starts a chat from a suggestion", async ({
  page,
}) => {
  await guardFallbackBase(page);
  await page.goto("/");
  const starter = page.locator(".aui-starter-page");
  await expect(starter).toBeVisible();
  await expect(starter.getByText("Start chatting with agent:")).toBeVisible();
  await expect(starter.locator(".aui-starter-page-agent")).toContainText(
    "default",
  );
  await starter.locator(".aui-thread-welcome-suggestion").first().click();
  await waitForAssistantReply(page, "reply-1");
  await expect(starter).toHaveCount(0);
});
