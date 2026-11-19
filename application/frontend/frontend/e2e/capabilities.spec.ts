import { expect, test, type Page } from "@playwright/test";

/**
 * Capability-matrix e2e against the packaged backend.
 *
 * Four deployments serve the same static bundle with different manifests.
 * See `capabilities.config.ts` for the fixed ports and served capabilities.
 * Run with `pnpm test:capabilities` (rebuild `out/` first).
 */

const ASSISTANT_OFF = 18080;
const THREADLESS = 18081;
const TRANSCRIPTS_OFF = 18082;
const ADMIN_ENABLED = 18083;
const ADMIN_ERROR = 18084;

function origin(port: number): string {
  return `http://localhost:${port}`;
}

async function openFresh(page: Page, port: number) {
  await page.goto(origin(port));
  await page.evaluate(() => localStorage.clear());
  await page.reload();
}

async function sendMessage(page: Page, text: string) {
  const composer = page.getByLabel("Message input");
  await expect(composer).toBeVisible();
  await expect(composer).toBeEnabled({ timeout: 30_000 });
  await composer.fill(text);
  await composer.press("Enter");
}

test("assistant-disabled deployment renders a notice, not a chat", async ({
  page,
}) => {
  await openFresh(page, ASSISTANT_OFF);

  await expect(page.getByRole("status")).toContainText("assistant is disabled");
  await expect(page.getByLabel("Message input")).toHaveCount(0);
  // Capability gating must also hide navigation that leads to chat-only UI.
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
});

test("full preset without threads runs a single conversation", async ({
  page,
}) => {
  const threadRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/threads")) {
      threadRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  await openFresh(page, THREADLESS);

  await expect(page.getByLabel("Message input")).toBeVisible();
  // No sidebar, no thread-list items, no "new chat" affordance.
  await expect(page.locator(".aui-thread-list-item-trigger")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "New Thread" })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Toggle Sidebar" }),
  ).toHaveCount(0);

  await sendMessage(page, "threadless hello");
  await expect(page.locator('[data-role="assistant"]')).toContainText(
    "reply-1",
  );

  // The conversation is transport-only: no thread list, initialization, or
  // transcript traffic may be attempted.
  expect(threadRequests).toEqual([]);
});

test("transcripts-off deployment never writes messages and forgets on reload", async ({
  page,
}) => {
  const messageWrites: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET" && request.url().includes("/messages")) {
      messageWrites.push(`${request.method()} ${request.url()}`);
    }
  });

  await openFresh(page, TRANSCRIPTS_OFF);

  await sendMessage(page, "ephemeral turn");
  await expect(page.locator('[data-role="assistant"]')).toContainText(
    "reply-1",
  );

  // Give the debounced synchronizer a chance to (wrongly) fire.
  await page.waitForTimeout(1500);
  expect(messageWrites).toEqual([]);

  // Without transcript storage the turn cannot be hydrated after reload.
  await page.reload();
  await expect(page.getByLabel("Message input")).toBeVisible();
  await expect(page.locator('[data-role="assistant"]')).toHaveCount(0);
});

test("admin tool capability exposes the header action without RAG calls", async ({
  page,
}) => {
  const ragRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/tools/web_rag")) {
      ragRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  await openFresh(page, ADMIN_ENABLED);

  const admin = page.getByRole("link", { name: "Admin" });
  await expect(admin).toBeVisible();
  await admin.click();

  await expect(page).toHaveURL(/\/admin\/?$/);
  await expect(page.getByText(/Web RAG capability is disabled/)).toBeVisible();
  // Admin without Web RAG must not poll the RAG status endpoints.
  expect(ragRequests).toEqual([]);
});

test("admin failures are visible, recoverable, and accessible", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto(`${origin(ADMIN_ERROR)}/admin/`);

  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert.getByRole("button", { name: "Retry" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh" })).toBeEnabled();
  await expect(page.getByLabel("Test search query")).toBeVisible();

  const unnamedButtons = await page
    .getByRole("button")
    .evaluateAll(
      (buttons) =>
        buttons.filter(
          (button) =>
            !(button.textContent ?? "").trim() &&
            !button.getAttribute("aria-label"),
        ).length,
    );
  expect(unnamedButtons).toBe(0);
  expect(pageErrors).toEqual([]);
});
