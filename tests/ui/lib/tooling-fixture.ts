import type { Page } from "@playwright/test";
import { mockTurnDetails } from "./turn-details-fixture";

export function toolingManifest(apiBase: string, preset: "minimal" | "full") {
  return {
    version: 1, api_base: apiBase, ui_preset: preset,
    features: { assistant: true, agents: false, threads: true, transcripts: true },
    tooling: { enabled: true, tool_names: ["divide", "get_weather", "web_rag", "render_graph"] },
    tools: { web_rag: { enabled: false, status_path: null } },
    presentation: { questions: [
      { id: "hooks", label: "Explain React hooks", prompt: "Explain React hooks like useState and useEffect" },
      { id: "sql", label: "Write a SQL query", prompt: "Write a SQL query to find top customers" },
      { id: "meal", label: "Create a meal plan", prompt: "Create a meal plan for healthy weight loss" },
    ] },
  };
}

export async function mockTooling(
  page: Page,
  apiBase: string,
  preset: "minimal" | "full" = "full",
) {
  await mockTurnDetails(page, apiBase, []);
  const field = {
    label: "Decimal places",
    type: "integer",
    minimum: 0,
    maximum: 12,
    choices: [],
    scope: "conversation",
    effect: "next_turn",
  };
  let global = {
    revision: 0,
    global_revision: 0,
    toolsets: ["calculator", "weather"],
    catalog: [
      {
        id: "calculator",
        title: "Calculator",
        description: "Basic arithmetic.",
        available: true,
        selected: true,
        tools: [
          {
            id: "divide",
            title: "Divide",
            enabled: true,
            selected: true,
            available: true,
            config: { precision: 6 },
            fields: { precision: field },
          },
        ],
      },
      {
        id: "weather",
        title: "Demo weather",
        description: "Simulated weather.",
        available: true,
        selected: true,
        tools: [
          {
            id: "get_weather",
            title: "Weather",
            enabled: true,
            selected: true,
            available: true,
            config: { units: "celsius" },
            fields: {
              units: {
                label: "Units",
                type: "enum",
                choices: ["celsius", "fahrenheit"],
                scope: "conversation",
                effect: "next_turn",
              },
            },
          },
        ],
      },
      {
        id: "web_rag",
        title: "Web RAG",
        description: "Optional retrieval.",
        available: false,
        selected: false,
        tools: [
          {
            id: "web_rag",
            title: "Retrieve documents",
            enabled: false,
            selected: true,
            available: false,
            config: {
              k: 5,
              embedding_provider: "fastembed",
              auto_bootstrap_web: false,
            },
            fields: {
              k: {
                ...field,
                label: "Retrieved chunks",
                minimum: 1,
                maximum: 20,
              },
              embedding_provider: {
                label: "Embedding provider",
                type: "enum",
                choices: ["fastembed", "openai"],
                scope: "startup",
                effect: "reindex",
              },
              auto_bootstrap_web: {
                label: "Bootstrap an empty index from the web",
                type: "boolean",
                choices: [],
                scope: "admin",
                effect: "next_turn",
              },
            },
          },
        ],
      },
    ],
  };
  let thread: any = null;
  const writes: {
    path: string;
    body: any;
    authorization: string | undefined;
  }[] = [];
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: toolingManifest(apiBase, preset),
    }),
  );
  const apply = (state: any, body: any) => ({
    ...state,
    revision: state.revision + 1,
    toolsets: body.toolsets,
    catalog: state.catalog.map((group: any) => ({
      ...group,
      selected: body.toolsets.includes(group.id),
      tools: group.tools.map((tool: any) => ({
        ...tool,
        selected: body.tools[tool.id]?.enabled ?? tool.selected,
        config: { ...tool.config, ...body.tools[tool.id]?.config },
      })),
    })),
  });
  await page.route(`${apiBase}/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    const isThread = path.endsWith("/tools") && path.startsWith("/threads/");
    if (!isThread && !path.startsWith("/tooling")) {
      await route.fallback();
      return;
    }
    const authorization = route.request().headers().authorization;
    if (path === "/tooling/admin" && authorization !== "Bearer admin-demo") {
      await route.fulfill({
        status: 403,
        json: { detail: "Administrator authorization required" },
      });
      return;
    }
    if (isThread && !thread) thread = structuredClone(global);
    let state: any = isThread ? thread : global;
    if (route.request().method() === "PUT") {
      const body = route.request().postDataJSON();
      if (
        body.revision !== state.revision ||
        (isThread && body.global_revision !== global.revision)
      ) {
        await route.fulfill({
          status: 409,
          json: { detail: "Tool settings changed. Refresh before saving." },
        });
        return;
      }
      writes.push({ path, body, authorization });
      state = apply(state, body);
      if (isThread) thread = state;
      else global = state;
    }
    state = structuredClone(state);
    state.global_revision = global.revision;
    if (isThread)
      state.catalog = state.catalog.map((group: any) => ({
        ...group,
        available: global.toolsets.includes(group.id),
        tools: group.tools.map((tool: any) => ({
          ...tool,
          available: global.toolsets.includes(group.id),
        })),
      }));
    await route.fulfill({ json: state });
  });
  return {
    writes,
    disableGlobally: () => {
      global.toolsets = [];
      global.revision++;
    },
  };
}
