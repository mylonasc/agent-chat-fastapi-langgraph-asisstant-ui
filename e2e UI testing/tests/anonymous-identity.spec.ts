import { expect, test } from "@playwright/test";

const storageKey = "agent-chat.anonymous-subject.v1";

test("anonymous browser subjects persist per profile and isolate profiles", async ({
  browser,
  page,
}) => {
  await page.goto("./");
  const first = await page.evaluate((key) => localStorage.getItem(key), storageKey);
  expect(first).toMatch(/^anon-/);

  await page.reload();
  const afterReload = await page.evaluate(
    (key) => localStorage.getItem(key),
    storageKey,
  );
  expect(afterReload).toBe(first);

  const otherContext = await browser.newContext();
  const otherPage = await otherContext.newPage();
  await otherPage.goto("./");
  const other = await otherPage.evaluate(
    (key) => localStorage.getItem(key),
    storageKey,
  );
  expect(other).toMatch(/^anon-/);
  expect(other).not.toBe(first);
  await otherContext.close();
});
