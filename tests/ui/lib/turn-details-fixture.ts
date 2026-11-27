import type { Page } from "@playwright/test";
import { createServer, type ServerResponse } from "node:http";
import { once } from "node:events";

export const detailsThreadId = "turn-details-thread";

export const toolPart = (name: string, result?: unknown) => ({
  type: "tool-call",
  toolCallId: `call-${name}`,
  toolName: name,
  args: { query: `input-for-${name}` },
  argsText: JSON.stringify({ query: `input-for-${name}` }),
  ...(result !== undefined ? { result } : {}),
});

export const storedMessage = (
  id: string,
  role: "user" | "assistant",
  content: unknown[],
  parentId?: string,
) => ({
  id,
  role,
  content,
  createdAt: "2026-01-01T00:00:00.000Z",
  ...(role === "assistant"
    ? { status: { type: "complete", reason: "stop" } }
    : {}),
  metadata: {
    custom: parentId ? { branchParentId: parentId } : {},
  },
});

const text = (value: string) => ({ type: "text", text: value });

export const turnDetailsHistory = [
  storedMessage("user-1", "user", [text("First question")]),
  storedMessage("assistant-1", "assistant", [
    toolPart("calculator", { answer: 42, longValue: "x".repeat(800) }),
    toolPart("web_search", {
      status: "completed",
      results: [{ link: "https://example.com", title: "Example source" }],
    }),
    text("First answer"),
  ]),
  storedMessage("user-2", "user", [text("Second question")]),
  storedMessage("assistant-2", "assistant", [
    toolPart("lookup", { answer: "second-result" }),
    text("Second answer"),
  ]),
  storedMessage("user-3", "user", [text("Third question")]),
  storedMessage("assistant-3", "assistant", [text("Third answer")]),
];

/** No model calls or real transcript writes are needed for DOM regressions. */
export async function mockTurnDetails(
  page: Page,
  apiBase: string,
  messages: unknown[] = turnDetailsHistory,
) {
  await page.addInitScript((id) => {
    localStorage.setItem("agent-chat.active-thread.v1", id);
  }, detailsThreadId);
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: {
        version: 1,
        api_base: apiBase,
        ui_preset: "full",
        features: {
          assistant: true,
          agents: false,
          threads: true,
          transcripts: true,
        },
        tools: {
          web_rag: { enabled: true, status_path: "/tools/web_rag/status" },
        },
      },
    }),
  );
  await page.route(`${apiBase}/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    if (path === "/api/config") {
      await route.fallback();
    } else if (path === "/threads") {
      const thread = {
        id:
          method === "GET"
            ? detailsThreadId
            : route.request().postDataJSON().localId,
        title: "Details test chat",
      };
      await route.fulfill({ json: method === "GET" ? [thread] : thread });
    } else if (path.endsWith("/messages")) {
      await route.fulfill({
        json: {
          messages:
            method === "GET" && path.includes(detailsThreadId) ? messages : [],
        },
      });
    } else if (path.endsWith("/feedback")) {
      await route.fulfill({ status: 404, json: { detail: "No feedback" } });
    } else if (path === "/tools/web_rag/status") {
      await route.fulfill({
        json: { index: { source_count: 0, document_count: 0 }, jobs: [] },
      });
    } else if (path.startsWith("/threads/")) {
      await route.fulfill({
        json: { id: path.split("/")[2], title: "Details test chat" },
      });
    } else {
      await route.fulfill({ json: {} });
    }
  });
}

/** A controllable real HTTP stream: Playwright route.fulfill buffers bodies. */
export async function mockStreamingTurn(page: Page) {
  let response: ServerResponse | undefined;
  let graphMessages: unknown[] = [];
  const writeState = () => {
    response?.write(
      `aui-state:${JSON.stringify([
        { type: "set", path: [], value: { messages: graphMessages } },
      ])}\n`,
    );
  };
  const server = createServer(async (request, res) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "*");
    if (request.method === "OPTIONS") {
      res.writeHead(204).end();
      return;
    }
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const payload = JSON.parse(Buffer.concat(chunks).toString());
    const prompt = payload.commands[0].message;
    graphMessages = [
      { id: prompt.id, type: "human", content: "Stream a tool" },
      {
        id: "stream-ai",
        type: "ai",
        content: "Checking the tool.",
        tool_calls: [
          {
            id: "slow-call",
            name: "slow_tool",
            args: { query: "stream-input" },
          },
        ],
      },
    ];
    response = res;
    res.writeHead(200, {
      "Content-Type": "text/plain; charset=utf-8",
      "x-vercel-ai-data-stream": "v1",
    });
    writeState();
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  if (!address || typeof address === "string")
    throw new Error("No fixture port");
  const origin = `http://127.0.0.1:${address.port}`;
  await mockTurnDetails(page, origin, []);
  await page.route(`${origin}/assistant`, (route) => route.continue());

  return {
    complete: () => {
      if (!response) throw new Error("The streaming request has not started");
      graphMessages.push(
        {
          type: "tool",
          tool_call_id: "slow-call",
          name: "slow_tool",
          content: "streamed-result",
        },
        { type: "ai", id: "final-ai", content: "Finished streaming answer" },
      );
      writeState();
      response.end(
        'd:{"finishReason":"stop","usage":{"promptTokens":0,"completionTokens":0}}\n',
      );
    },
    close: async () => {
      server.closeAllConnections();
      await new Promise<void>((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      );
    },
  };
}
