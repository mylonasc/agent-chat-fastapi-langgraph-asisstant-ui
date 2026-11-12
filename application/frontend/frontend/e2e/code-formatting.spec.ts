import { expect, test } from "@playwright/test";

/**
 * Syntax-highlighting regression test. Uses the real packaged transport and
 * the deterministic EchoFake, not Ollama. The fake answers the
 * ``[[syntax-highlight-demo]]`` prompt with one fenced block per language.
 */

const HIGHLIGHTED_LANGUAGES = [
  "bash",
  "c",
  "clojure",
  "cpp",
  "csharp",
  "css",
  "dart",
  "diff",
  "docker",
  "elixir",
  "go",
  "graphql",
  "haskell",
  "ini",
  "java",
  "javascript",
  "json",
  "jsx",
  "kotlin",
  "less",
  "lua",
  "makefile",
  "markdown",
  "markup",
  "objectivec",
  "perl",
  "php",
  "powershell",
  "python",
  "r",
  "ruby",
  "rust",
  "sass",
  "scala",
  "scss",
  "sql",
  "swift",
  "toml",
  "tsx",
  "typescript",
  "yaml",
];

// Aliases resolve to their canonical grammar but keep the block readable.
const ALIASED_LANGUAGES = ["python", "bash", "yaml", "markup", "cpp", "csharp"];

test("renders every supported fence as highlighted code @packaged", async ({
  page,
}) => {
  await page.goto("/");
  const input = page.getByLabel("Message input", { exact: true });
  await expect(input).toBeEnabled({ timeout: 30_000 });
  await input.fill("[[syntax-highlight-demo]]");
  await input.press("Enter");

  const assistant = page.locator('[data-role="assistant"]').first();
  await expect(assistant).toContainText("println!", { timeout: 60_000 });
  await expect(
    page.getByRole("button", { name: "Stop generating", exact: true }),
  ).toHaveCount(0);

  const blocks = assistant.locator("pre[data-highlighted]");
  const expectedCount = HIGHLIGHTED_LANGUAGES.length + ALIASED_LANGUAGES.length;
  await expect(blocks).toHaveCount(expectedCount);

  for (const language of HIGHLIGHTED_LANGUAGES) {
    await expect(
      assistant.locator(`pre[data-language="${language}"]`).first(),
      `${language} fence must render a highlighted block`,
    ).toHaveAttribute("data-highlighted", "true");
  }

  for (const language of ALIASED_LANGUAGES) {
    await expect(
      assistant.locator(`pre[data-language="${language}"]`).last(),
      `${language} alias must resolve to its canonical grammar`,
    ).toHaveAttribute("data-highlighted", "true");
  }

  // The canonical fence and its alias should both resolve to one grammar
  // instead of one falling back to plain text.
  for (const [language, count] of [
    ["python", 2],
    ["bash", 2],
    ["yaml", 2],
    ["markup", 2],
    ["cpp", 2],
    ["csharp", 2],
    ["c", 1],
  ] as const) {
    await expect(
      assistant.locator(`pre[data-language="${language}"]`),
      `${language} block count`,
    ).toHaveCount(count);
  }
  await expect(
    assistant.locator('pre[data-language="cpp"]').last(),
  ).toContainText("int main() { return 0; }");
  await expect(
    assistant.locator('pre[data-language="csharp"]').last(),
  ).toContainText("class App {}");

  // Representative grammars must emit real Prism token spans, not plain text.
  // react-syntax-highlighter applies the oneDark theme as inline styles, so
  // token spans are classed `token` and carry a colour rather than a
  // keyword-specific class name.
  const tokenChecks = [
    "python",
    "javascript",
    "json",
    "yaml",
    "sql",
    "markdown",
    "bash",
    "rust",
    "css",
  ];

  for (const language of tokenChecks) {
    const token = assistant
      .locator(`pre[data-language="${language}"]`)
      .first()
      .locator(".token")
      .first();
    await expect(
      token,
      `${language} block should contain a styled Prism token`,
    ).toBeVisible();
    await expect(token).toHaveAttribute("style", /color/);
  }

  // The code content itself is not lost while highlighting.
  await expect(
    assistant.locator('pre[data-language="python"]').first(),
  ).toContainText("def greet(name: str) -> str:");
  await expect(
    assistant.locator('pre[data-language="yaml"]').first(),
  ).toContainText("name: local-chat");
});
