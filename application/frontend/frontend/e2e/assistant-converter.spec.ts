import { expect, test } from "@playwright/test";
import type { LangChainMessage } from "@assistant-ui/react-langgraph";

import {
  createChatMessageConverter,
  type ChatTransportMessage,
  type ChatTransportState,
} from "../lib/assistant/converter";
import type {
  AssistantTransportCommand,
  AssistantTransportConnectionMetadata,
  ThreadMessage,
} from "../lib/assistant/runtime-compat";

const fullConverter = createChatMessageConverter({
  syntheticIdPrefix: "legacy-",
  optimisticHumans: "while-sending",
  hydrateStoredUiTranscript: true,
});

const minimalConverter = createChatMessageConverter({
  syntheticIdPrefix: "m-",
  optimisticHumans: "until-echoed",
  hydrateStoredUiTranscript: false,
});

function metadata(
  overrides: Partial<AssistantTransportConnectionMetadata> = {},
): AssistantTransportConnectionMetadata {
  return {
    pendingCommands: [],
    isSending: false,
    toolStatuses: {},
    ...overrides,
  };
}

const pendingHuman: AssistantTransportCommand = {
  type: "add-message",
  message: { role: "user", parts: [{ type: "text", text: "Hello" }] },
};

function textOf(message: ThreadMessage): string {
  return message.content
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("");
}

test("full preset hydrates stored UI transcripts verbatim", () => {
  const stored = [
    {
      id: "user-1",
      role: "user",
      content: [{ type: "text", text: "Draw a graph" }],
    },
    {
      id: "assistant-1",
      role: "assistant",
      content: [
        { type: "text", text: "Here it is" },
        {
          type: "tool-call",
          toolCallId: "call-1",
          toolName: "graph",
          args: { nodes: 2 },
          argsText: '{"nodes":2}',
          result: { ok: true },
        },
      ],
    },
  ] satisfies ChatTransportMessage[];

  const result = fullConverter({ messages: stored }, metadata());

  // Same array, no LangChain round-trip: rich parts and stored IDs survive.
  expect(result.messages).toBe(stored);
  expect(result.messages[1]?.content[1]).toMatchObject({
    type: "tool-call",
    toolCallId: "call-1",
    result: { ok: true },
  });
  expect(result.isRunning).toBe(false);
});

test("full preset only surfaces optimistic humans while sending", () => {
  const state: ChatTransportState = { messages: [] };

  const idle = fullConverter(state, metadata());
  expect(idle.messages).toHaveLength(0);

  const sending = fullConverter(
    state,
    metadata({ isSending: true, pendingCommands: [pendingHuman] }),
  );
  expect(sending.messages).toHaveLength(1);
  expect(sending.messages[0]?.role).toBe("user");
  expect(textOf(sending.messages[0]!)).toBe("Hello");
  expect(sending.isRunning).toBe(true);
});

test("minimal preset keeps optimistic humans until the server echoes them", () => {
  const state: ChatTransportState = { messages: [] };

  const idle = minimalConverter(
    state,
    metadata({ pendingCommands: [pendingHuman] }),
  );
  expect(idle.messages).toHaveLength(1);
  expect(idle.messages[0]?.role).toBe("user");
  expect(textOf(idle.messages[0]!)).toBe("Hello");

  const echoed: ChatTransportState = {
    messages: [{ type: "human", content: "Hello" }],
  };
  const afterEcho = minimalConverter(
    echoed,
    metadata({ pendingCommands: [pendingHuman] }),
  );
  expect(afterEcho.messages).toHaveLength(1);
  expect(textOf(afterEcho.messages[0]!)).toBe("Hello");
});

test("full preset prefers the echoed server message over the pending one", () => {
  const state: ChatTransportState = {
    messages: [{ type: "human", content: "Hello from server" }],
  };

  const result = fullConverter(
    state,
    metadata({ isSending: true, pendingCommands: [pendingHuman] }),
  );

  expect(result.messages).toHaveLength(1);
  expect(textOf(result.messages[0]!)).toBe("Hello from server");
});

test("preserves source IDs and merges tool calls into the assistant turn", () => {
  const state: ChatTransportState = {
    messages: [
      { id: "human-1", type: "human", content: "What is Elassona?" },
      {
        id: "ai-1",
        type: "ai",
        content: "",
        tool_calls: [
          { id: "call-1", name: "web_rag", args: { query: "Elassona" } },
        ],
      },
      {
        id: "tool-1",
        type: "tool",
        content: "Elassona is a town.",
        tool_call_id: "call-1",
        name: "web_rag",
        status: "success",
      },
    ] satisfies LangChainMessage[],
  };

  const result = fullConverter(state, metadata());

  // The AI + tool round trip joins into one assistant message.
  expect(result.messages).toHaveLength(2);
  expect(result.messages.map((message) => message.id)).toEqual([
    "human-1",
    "ai-1",
  ]);

  const assistant = result.messages[1]!;
  const toolCall = assistant.content.find((part) => part.type === "tool-call");
  expect(toolCall).toMatchObject({
    type: "tool-call",
    toolCallId: "call-1",
    toolName: "web_rag",
    result: "Elassona is a town.",
  });
});

test("synthetic IDs are prefixed and stable across identical conversions", () => {
  const state: ChatTransportState = {
    messages: [
      { id: "", type: "human", content: "Hi" },
      { id: "", type: "ai", content: "Hello" },
    ] satisfies LangChainMessage[],
  };

  const first = fullConverter(state, metadata());
  const second = fullConverter(state, metadata());

  expect(first.messages.map((message) => message.id)).toEqual([
    "legacy-0",
    "legacy-1",
  ]);
  expect(second.messages.map((message) => message.id)).toEqual(
    first.messages.map((message) => message.id),
  );
});

test("minimal preset uses its own synthetic ID prefix", () => {
  const state: ChatTransportState = {
    messages: [
      { id: "", type: "human", content: "Hi" },
    ] satisfies LangChainMessage[],
  };

  const result = minimalConverter(state, metadata());
  expect(result.messages[0]?.id).toBe("m-0");
});
