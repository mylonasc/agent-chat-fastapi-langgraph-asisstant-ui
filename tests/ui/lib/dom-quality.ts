import { expect, Page } from "@playwright/test";

export async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(dimensions.scrollWidth, "document has horizontal overflow").toBeLessThanOrEqual(
    dimensions.clientWidth + 1,
  );
}

export async function expectNoDuplicateIds(page: Page) {
  const duplicates = await page.evaluate(() => {
    const counts = new Map<string, number>();
    document.querySelectorAll<HTMLElement>("[id]").forEach((element) => {
      counts.set(element.id, (counts.get(element.id) ?? 0) + 1);
    });
    return [...counts.entries()].filter(([, count]) => count > 1);
  });

  expect(duplicates, "duplicate DOM ids").toEqual([]);
}

export async function expectVisibleControlsHaveNames(page: Page) {
  const unnamed = await page.evaluate(() => {
    const selector = [
      "button",
      "a[href]",
      "input:not([type='hidden'])",
      "textarea",
      "select",
      "[role='button']",
    ].join(",");

    return [...document.querySelectorAll<HTMLElement>(selector)]
      .filter((element) => {
        const style = getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      })
      .filter((element) => {
        const labels = "labels" in element
          ? [...((element as HTMLInputElement).labels ?? [])].map((label) => label.textContent ?? "").join(" ")
          : "";
        const name = [
          element.getAttribute("aria-label"),
          element.getAttribute("aria-labelledby"),
          element.getAttribute("title"),
          element.getAttribute("alt"),
          labels,
          element.textContent,
        ]
          .filter(Boolean)
          .join(" ")
          .trim();
        return name.length === 0;
      })
      .map((element) => ({
        tag: element.tagName.toLowerCase(),
        className: element.className,
        outerHTML: element.outerHTML.slice(0, 240),
      }));
  });

  expect(unnamed, "visible interactive controls without accessible names").toEqual([]);
}

export async function expectInsideViewport(page: Page, selector: string) {
  const locator = page.locator(selector).first();
  const edge = async (name: "left" | "right" | "top" | "bottom") =>
    locator.evaluate((element, edgeName) => {
      const box = element.getBoundingClientRect();
      return {
        value: box[edgeName],
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
      };
    }, name);

  await expect.poll(async () => (await edge("left")).value).toBeGreaterThanOrEqual(-1);
  await expect.poll(async () => {
    const result = await edge("right");
    return result.value - result.viewportWidth;
  }).toBeLessThanOrEqual(1);
  await expect.poll(async () => (await edge("top")).value).toBeGreaterThanOrEqual(-1);
  await expect.poll(async () => {
    const result = await edge("bottom");
    return result.value - result.viewportHeight;
  }).toBeLessThanOrEqual(1);
}
