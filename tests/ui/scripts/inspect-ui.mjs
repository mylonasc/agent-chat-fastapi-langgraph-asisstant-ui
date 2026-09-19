import { chromium } from "@playwright/test";

const app = process.argv[2];
if (!new Set(["full", "minimal"]).has(app)) {
  console.error("Usage: node scripts/inspect-ui.mjs <full|minimal> [--mobile] [--url URL]");
  process.exit(2);
}

const mobile = process.argv.includes("--mobile");
const urlIndex = process.argv.indexOf("--url");
const configuredUrl = urlIndex >= 0 ? process.argv[urlIndex + 1] : undefined;
const url = configuredUrl ?? (app === "full" ? "http://localhost:3001" : "http://localhost:3000");
const viewport = mobile ? { width: 412, height: 915 } : { width: 1440, height: 900 };

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport });

try {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.locator("main").waitFor({ state: "visible" });
  const report = await page.evaluate(({ appName, inspectedUrl, viewportSize }) => {
    const isVisible = (element) => {
      const style = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
    };
    const accessibleName = (element) => {
      const labels = "labels" in element
        ? [...(element.labels ?? [])].map((label) => label.textContent ?? "").join(" ")
        : "";
      return [
        element.getAttribute("aria-label"),
        element.getAttribute("aria-labelledby"),
        element.getAttribute("title"),
        labels,
        element.textContent,
      ]
        .filter(Boolean)
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
    };

    const interactive = [...document.querySelectorAll(
      "button, a[href], input:not([type='hidden']), textarea, select, [role='button']",
    )]
      .filter(isVisible)
      .map((element) => {
        const box = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          role: element.getAttribute("role"),
          name: accessibleName(element),
          disabled: "disabled" in element ? element.disabled : element.getAttribute("aria-disabled") === "true",
          box: {
            x: Math.round(box.x),
            y: Math.round(box.y),
            width: Math.round(box.width),
            height: Math.round(box.height),
          },
        };
      });

    const idCounts = new Map();
    document.querySelectorAll("[id]").forEach((element) => {
      idCounts.set(element.id, (idCounts.get(element.id) ?? 0) + 1);
    });

    return {
      app: appName,
      url: inspectedUrl,
      viewport: viewportSize,
      document: {
        title: document.title,
        lang: document.documentElement.lang,
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      },
      landmarks: {
        headers: document.querySelectorAll("header").length,
        main: document.querySelectorAll("main").length,
        navigation: document.querySelectorAll("nav").length,
        aside: document.querySelectorAll("aside").length,
      },
      headings: [...document.querySelectorAll("h1, h2, h3, h4, h5, h6")]
        .filter(isVisible)
        .map((heading) => ({ level: Number(heading.tagName.slice(1)), text: heading.textContent?.trim() })),
      interactive,
      findings: {
        unnamedControls: interactive.filter((control) => !control.name),
        targetsUnder32px: interactive.filter(
          (control) => control.box.width < 32 || control.box.height < 32,
        ),
        duplicateIds: [...idCounts.entries()].filter(([, count]) => count > 1),
      },
    };
  }, { appName: app, inspectedUrl: url, viewportSize: viewport });

  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} finally {
  await browser.close();
}
