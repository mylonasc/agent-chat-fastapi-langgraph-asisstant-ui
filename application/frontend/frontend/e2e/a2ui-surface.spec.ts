import { expect, test, type Page } from "@playwright/test";

/**
 * A2UI surface e2e: deterministic tool-call -> surface -> action loop.
 *
 * Backend is helpers/fake_backend.py in E2E_A2UI mode: the real
 * render_a2ui_demo tool behind a fake model, so the envelope bytes are
 * exactly what production agents emit. No network, no credentials.
 *
 * Rebuild `out/` with `pnpm build` first so the served bundle matches
 * `components/` + `app/` sources, and run with the package venv:
 *
 *   E2E_PYTHON=../../../packages/agent-chat-minimal/.venv/bin/python \
 *     pnpm playwright test -c e2e/a2ui-surface.config.ts
 */
async function sendMessage(page: Page, text: string) {
  const composer = page.getByLabel("Message input");
  await expect(composer).toBeEnabled({ timeout: 30_000 });
  await composer.fill(text);
  await composer.press("Enter");
}

test("a2ui card renders in-thread and Confirm round-trips as chat text @packaged", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));

  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.getByLabel("Message input")).toBeVisible();

  await sendMessage(page, "show me the booking card");

  const assistant = page.locator('[data-role="assistant"]').last();
  await expect(assistant.getByText("Book Your Table")).toBeVisible({
    timeout: 60_000,
  });
  await expect(assistant.getByText("E2E card body.")).toBeVisible();
  const confirm = assistant.getByRole("button", { name: /confirm/i });
  await expect(confirm).toBeVisible();

  await confirm.click();
  const actionUser = page
    .locator('[data-role="user"]')
    .filter({ hasText: "a2ui-action confirm_booking" });
  await expect(actionUser).toBeVisible({ timeout: 30_000 });

  // Durable-first: the dedicated endpoint stored the canonical message
  // server-side (not just locally), in the canonical compact-JSON form.
  const subject = await page.evaluate(() =>
    window.localStorage.getItem("agent-chat.anonymous-subject.v1"),
  );
  const threads = await page.request
    .get("/threads", { headers: { "x-agent-chat-subject": String(subject) } })
    .then((r) => r.json());
  const messages = await page.request
    .get(`/threads/${threads[0].id}/messages`, {
      headers: { "x-agent-chat-subject": String(subject) },
    })
    .then((r) => r.json());
  const texts = (messages.messages as unknown[])
    .flatMap((m) =>
      Array.isArray((m as { content?: unknown }).content)
        ? (m as { content: { text?: string }[] }).content
        : [],
    )
    .map((p) => p.text ?? "");
  expect(texts).toContain(
    '[a2ui-action confirm_booking] {"name":"confirm_booking","context":{"surfaceId":"demo-card"}}',
  );

  await expect(errors).toEqual([]);
});

test("a2ui surface survives transcript reload @packaged", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.getByLabel("Message input")).toBeVisible();

  await sendMessage(page, "show me the booking card");
  const assistant = page.locator('[data-role="assistant"]').last();
  await expect(assistant.getByText("Book Your Table")).toBeVisible({
    timeout: 60_000,
  });

  // Let the debounced transcript synchronizer persist, then reload: the
  // stored verbatim transcript must re-render the same surface.
  await page.waitForTimeout(2500);
  await page.reload();
  await expect(
    page.locator('[data-role="assistant"]').last().getByText("Book Your Table"),
  ).toBeVisible({ timeout: 60_000 });
});

test("custom NetworkGraph resolves path bindings and renders D3 svg @packaged", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));

  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.getByLabel("Message input")).toBeVisible();

  await sendMessage(page, "show me a network graph");
  const assistant = page.locator('[data-role="assistant"]').last();
  await expect(assistant.getByText(/Network \(2 nodes, 1 edges\)/)).toBeVisible({
    timeout: 60_000,
  });
  // ForceGraph paints nodes as svg circles; two nodes expected.
  await expect
    .poll(async () => assistant.locator("svg circle").count(), {
      timeout: 30_000,
    })
    .toBe(2);
  await expect(errors).toEqual([]);
});
