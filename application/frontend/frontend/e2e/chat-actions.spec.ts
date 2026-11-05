import { expect, test, type Page } from "@playwright/test";

/**
 * Expected-behavior regression tests: failures intentionally expose broken
 * controls rather than accepting disabled buttons or marking defects xfail.
 * Uses the real packaged transport + deterministic EchoFake, not Ollama.
 * Tracking issue: https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/71
 */
async function send(page: Page, text: string, turn: number) {
  const input = page.getByLabel("Message input", { exact: true });
  await expect(input).toBeEnabled({ timeout: 30_000 });
  await input.fill(text);
  await input.press("Enter");
  await expect(
    page.locator('[data-role="assistant"]').nth(turn - 1),
  ).toContainText(`reply-${turn}`);
  await expect(
    page.getByRole("button", { name: "Stop generating", exact: true }),
  ).toHaveCount(0);
}

async function waitForStoredCount(page: Page, count: number) {
  await expect
    .poll(
      async () =>
        page.evaluate(async () => {
          const subject = localStorage.getItem(
            "agent-chat.anonymous-subject.v1",
          );
          const headers: Record<string, string> = subject
            ? { "x-agent-chat-subject": subject }
            : {};
          const threadId = localStorage.getItem("agent-chat.active-thread.v1");
          if (!threadId) return -1;
          const data = await fetch(`/threads/${threadId}/messages`, {
            headers,
          }).then((r) => r.json());
          return data.messages?.length ?? -1;
        }),
      { timeout: 30_000 },
    )
    .toBe(count);
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Message input", { exact: true })).toBeVisible();
});

test("recompute regenerates the assistant response for the same prompt @packaged", async ({
  page,
}) => {
  await send(page, "original prompt", 1);
  const assistant = page.locator('[data-role="assistant"]').first();
  const originalId = await assistant.getAttribute("data-message-id");
  const refresh = assistant.getByRole("button", {
    name: "Refresh",
    exact: true,
  });
  let generationRequests = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/assistant(?:\/[^/?]+)?$/.test(request.url())
    ) {
      generationRequests++;
    }
  });

  // Expected: the visible recompute control is actionable after generation.
  await expect(refresh).toBeEnabled();
  await refresh.click();
  await expect
    .poll(() => generationRequests, {
      message: "Refresh must send a new assistant generation request",
    })
    .toBe(1);
  await expect(assistant).toContainText("reply-1");
  await expect(assistant).not.toHaveAttribute("data-message-id", originalId!);
  await expect(page.locator('[data-role="user"]')).toHaveCount(1);
  await waitForStoredCount(page, 3);
  await page.reload();
  await expect(page.locator('[data-role="user"]')).toHaveCount(1);
  await expect(page.locator('[data-role="assistant"]')).toHaveCount(1);
  const previous = page
    .locator('[data-role="assistant"] .aui-branch-picker-root')
    .getByRole("button", { name: "Previous", exact: true });
  await previous.click();
  await expect(page.locator('[data-role="assistant"]')).toHaveAttribute(
    "data-message-id",
    originalId!,
  );
});

test("edit resubmits a sent user message as an alternative conversation @packaged", async ({
  page,
}) => {
  await send(page, "original prompt", 1);
  const user = page.locator('[data-role="user"]').first();
  await user.hover();
  const edit = user.getByRole("button", { name: "Edit", exact: true });

  // Expected: edit opens a prefilled editor, not an inert pencil icon.
  await expect(edit).toBeEnabled();
  await edit.click();
  const editor = page.locator(".aui-edit-composer-input");
  await expect(editor).toHaveValue("original prompt");
  await editor.fill("alternative prompt");
  const updated = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/assistant(?:\/[^/?]+)?$/.test(response.url()),
  );
  await page
    .getByRole("button", { name: "Update message", exact: true })
    .click();
  const response = await updated;
  expect(response.ok()).toBe(true);
  expect(JSON.stringify(response.request().postDataJSON())).toContain(
    "alternative prompt",
  );
  await expect(page.locator('[data-role="user"]').first()).toContainText(
    "alternative prompt",
  );
  await expect(page.locator('[data-role="assistant"]').first()).toContainText(
    "reply-1",
  );
  // A real edit creates a meaningful alternative: Previous restores the original.
  await page
    .locator(".aui-user-branch-picker")
    .first()
    .getByRole("button", { name: "Previous", exact: true })
    .click();
  await expect(page.locator('[data-role="user"]').first()).toContainText(
    "original prompt",
  );
  await waitForStoredCount(page, 4);
  await page.reload();
  await expect(page.locator('[data-role="user"]')).toHaveCount(1);
  await page
    .locator(".aui-user-branch-picker")
    .getByRole("button", { name: "Previous", exact: true })
    .click();
  await expect(page.locator('[data-role="user"]')).toContainText(
    "original prompt",
  );
});

test("editing an earlier turn truncates inference history but retains its original continuation @packaged", async ({
  page,
}) => {
  await send(page, "first prompt", 1);
  await send(page, "second prompt", 2);
  const user = page.locator('[data-role="user"]').first();
  await user.hover();
  await user.getByRole("button", { name: "Edit", exact: true }).click();
  await page
    .locator(".aui-edit-composer-input")
    .fill("replacement first prompt");
  await page
    .getByRole("button", { name: "Update message", exact: true })
    .click();
  await expect(page.locator('[data-role="assistant"]')).toHaveCount(1);
  await expect(page.locator('[data-role="assistant"]')).toContainText(
    "reply-1",
  );
  await page
    .locator(".aui-user-branch-picker")
    .getByRole("button", { name: "Previous", exact: true })
    .click();
  await expect(page.locator('[data-role="user"]').nth(1)).toContainText(
    "second prompt",
  );
  await expect(page.locator('[data-role="assistant"]').nth(1)).toContainText(
    "reply-2",
  );
});

test("ordinary sends do not create a phantom 2/2 branch on the first message @packaged", async ({
  page,
}, testInfo) => {
  await page.evaluate(() => {
    const observed: string[] = [];
    (
      window as Window & { observedBranchStates?: string[] }
    ).observedBranchStates = observed;
    new MutationObserver(() => {
      for (const node of document.querySelectorAll(
        ".aui-user-branch-picker .aui-branch-picker-state",
      )) {
        const state = node.textContent?.replace(/\s+/g, "").trim();
        if (state && !observed.includes(state)) observed.push(state);
      }
    }).observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
    });
  });
  await send(page, "first prompt", 1);
  await waitForStoredCount(page, 2);
  await send(page, "second prompt", 2);
  await waitForStoredCount(page, 4);
  const observed = await page.evaluate(
    () =>
      (window as Window & { observedBranchStates?: string[] })
        .observedBranchStates ?? [],
  );
  await testInfo.attach("observed-user-branch-states", {
    body: JSON.stringify(observed),
    contentType: "application/json",
  });

  // No edit/recompute occurred: there is only one branch, so hide its picker.
  await expect(page.locator(".aui-user-branch-picker")).toHaveCount(0);
  await expect(page.locator(".aui-branch-picker-state")).toHaveCount(0);
  expect
    .soft(
      observed,
      "Normal sends must not introduce even transient alternate user branches",
    )
    .not.toContain("2/2");
  await page.reload();
  await expect(page.locator('[data-role="assistant"]').nth(1)).toContainText(
    "reply-2",
  );
  await expect(page.locator(".aui-branch-picker-state")).toHaveCount(0);
  await send(page, "third prompt after reload", 3);
  await waitForStoredCount(page, 6);
  await expect(page.locator(".aui-branch-picker-state")).toHaveCount(0);
});
