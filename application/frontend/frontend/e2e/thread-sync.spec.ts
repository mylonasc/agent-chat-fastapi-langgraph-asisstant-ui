import { expect, test, type Page, type Response } from "@playwright/test";

/**
 * Thread-sync e2e against the packaged backend (same-origin UI + API) with a
 * deterministic echo fake agent (turn N answers `reply-N`).
 *
 * Run: `pnpm playwright test -c e2e/thread-sync.config.ts` from
 * `application/frontend/frontend` (rebuild `out/` with `pnpm build` first so
 * the served bundle matches `components/` + `app/` sources).
 */

interface BadResponse {
  status: number;
  method: string;
  url: string;
}

function trackResponses(page: Page) {
  const bad: BadResponse[] = [];
  page.on("response", (response: Response) => {
    const url = response.url();
    if (!url.includes("/threads") && !url.includes("/assistant")) return;
    const status = response.status();
    if (status === 409) {
      bad.push({ status, method: response.request().method, url });
    }
    // GET .../feedback 404 means "no rating yet" (pinned API contract) and
    // is swallowed by the client; every other 4xx is a sync defect.
    if (status >= 400 && status !== 409 && !url.includes("/feedback")) {
      bad.push({ status, method: response.request().method, url });
    }
  });
  return bad;
}

async function freshPage(page: Page) {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.getByLabel("Message input")).toBeVisible();
}

async function sendMessage(page: Page, text: string) {
  const composer = page.getByLabel("Message input");
  // The composer stays disabled until the thread is server-bound.
  await expect(composer).toBeEnabled({ timeout: 30_000 });
  await composer.fill(text);
  await composer.press("Enter");
}

async function expectReply(page: Page, text: string, nth = 0) {
  await expect(page.locator('[data-role="assistant"]').nth(nth)).toContainText(
    text,
    { timeout: 30_000 },
  );
}

/**
 * Wait until the transcript synchronizer has persisted every UI message.
 * Syncing is eventually consistent by design (debounced + retried), so any
 * reload or cross-check before this is racy: hydration can only restore
 * what is already stored.
 */
async function waitForStoredCount(page: Page, count: number) {
  await expect
    .poll(
      async () =>
        page.evaluate(async () => {
          const subject = localStorage.getItem("agent-chat.anonymous-subject.v1");
          const headers = subject ? { "x-agent-chat-subject": subject } : {};
          const threads = await fetch("/threads", { headers }).then((r) => r.json());
          if (!threads[0]) return -1;
          const messages = await fetch(`/threads/${threads[0].id}/messages`, {
            headers,
          }).then((r) => r.json());
          return (messages.messages as unknown[]).length;
        }),
      { timeout: 30_000 },
    )
    .toBe(count);
}

async function orderedRoles(page: Page): Promise<string[]> {
  const roles = page.locator('[data-role="user"], [data-role="assistant"]');
  const count = await roles.count();
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const role = await roles.nth(i).getAttribute("data-role");
    const text = ((await roles.nth(i).innerText()) ?? "").replace(/\s+/g, " ").trim();
    out.push(`${role}:${text.slice(0, 24)}`);
  }
  return out;
}

test("two turns render in order and survive reload without sync errors", async ({
  page,
}) => {
  const bad = trackResponses(page);
  await freshPage(page);

  await sendMessage(page, "first");
  await expectReply(page, "reply-1");
  await sendMessage(page, "second");
  await expectReply(page, "reply-2", 1);

  const before = await orderedRoles(page);
  expect(before).toHaveLength(4);
  expect(before[0]).toMatch(/^user:first/);
  expect(before[1]).toMatch(/^assistant:reply-1/);
  expect(before[2]).toMatch(/^user:second/);
  expect(before[3]).toMatch(/^assistant:reply-2/);
  // No orphaned pending nodes may linger as alternate branches: the first
  // message must not offer branch navigation.
  await expect(page.getByText(/Previous.*Next/)).toHaveCount(0);

  await waitForStoredCount(page, 4);
  await page.reload();
  await expectReply(page, "reply-2", 1);
  const after = await orderedRoles(page);
  expect(after).toEqual(before);

  expect(bad).toEqual([]);
});

test("feedback persists across reload", async ({ page }) => {
  const bad = trackResponses(page);
  await freshPage(page);

  await sendMessage(page, "rate me");
  await expectReply(page, "reply-1");

  const helpful = page.getByRole("button", { name: "Mark response helpful" });
  await expect(helpful).toBeVisible();
  await helpful.click();
  await expect(helpful).toHaveAttribute("aria-pressed", "true");

  await waitForStoredCount(page, 2);
  await page.reload();
  await expectReply(page, "reply-1");
  await expect(
    page.getByRole("button", { name: "Mark response helpful" }),
  ).toHaveAttribute("aria-pressed", "true");

  expect(bad).toEqual([]);
});

test("switching threads preserves each transcript", async ({ page }) => {
  const bad = trackResponses(page);
  await freshPage(page);

  await sendMessage(page, "thread one");
  await expectReply(page, "reply-1");

  await page.getByRole("button", { name: "New Thread" }).click();
  await sendMessage(page, "thread two");
  await expectReply(page, "reply-1");
  expect(await orderedRoles(page)).toHaveLength(2);

  // Newest thread first: switch back to the older thread and back again.
  const triggers = page.locator(".aui-thread-list-item-trigger");
  await expect(triggers).toHaveCount(2);
  await triggers.nth(1).click();
  await expect(page.locator('[data-role="user"]')).toContainText("thread one");
  expect(await orderedRoles(page)).toHaveLength(2);
  await triggers.nth(0).click();
  await expect(page.locator('[data-role="user"]')).toContainText("thread two");

  expect(bad).toEqual([]);
});
