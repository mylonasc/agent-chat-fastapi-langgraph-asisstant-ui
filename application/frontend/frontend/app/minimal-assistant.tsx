"use client";

import {
  AssistantRuntimeProvider,
  AssistantTransportConnectionMetadata,
  unstable_createMessageConverter as createMessageConverter,
  useAssistantTransportRuntime,
} from "@assistant-ui/react";
import {
  convertLangChainMessages,
  LangChainMessage,
} from "@assistant-ui/react-langgraph";
import { ReactNode } from "react";

import { Thread } from "@/components/assistant-ui/thread";
import { GraphToolUI } from "@/components/tools/GraphToolUI";
import { useApiClient } from "@/hooks/use-api-client";

type State = {
  messages: LangChainMessage[];
};

const LangChainMessageConverter = createMessageConverter(
  convertLangChainMessages,
);

const converter = (
  state: State,
  connectionMetadata: AssistantTransportConnectionMetadata,
) => {
  const serverMessages = state.messages || [];

  // Extract pending human messages from the transport layer.
  const pendingHumanMessages = connectionMetadata.pendingCommands
    .filter((cmd) => cmd.type === "add-message")
    .map((cmd) => ({
      type: "human" as const,
      content: [
        {
          type: "text" as const,
          text: cmd.message.parts
            .map((p) => (p.type === "text" ? p.text : ""))
            .join(""),
        },
      ],
    }));

  // The server echoes the human message back with a stable ID; until then
  // prepend the optimistic version to keep transcript order.
  const hasHumanInServer = serverMessages.some((m) => m.type === "human");
  const allMessages = hasHumanInServer
    ? serverMessages
    : [...pendingHumanMessages, ...serverMessages];
  const converted = LangChainMessageConverter.toThreadMessages(allMessages);
  // Keep converter/source IDs stable across renders; re-indexing on every
  // render would remap identities whenever pending messages shift positions.
  // Synthetic fallbacks use an "m-" prefix: bare-integer ids reorder inside
  // the UI runtime (integer-like keys sort before string keys).
  const positional = converted.length === allMessages.length;
  const threadMessages = converted.map((message, index) => ({
    ...message,
    id:
      message.id ||
      (positional
        ? String(
            (allMessages[index] as { id?: string } | undefined)?.id ??
              `m-${index}`,
          )
        : `m-${index}`),
  }));

  return {
    messages: threadMessages,
    isRunning: connectionMetadata.isSending,
  };
};

/**
 * Minimal preset: single-thread chat without thread-list/admin chrome.
 * The shared Thread view is reused; only the runtime composition differs.
 */
export function MinimalAssistant({ children }: { children?: ReactNode }) {
  const { client } = useApiClient();
  const runtime = useAssistantTransportRuntime({
    initialState: {
      messages: [],
    },
    api: client.assistantUrl(),
    headers: client.headers(),
    converter,
    onError: (error: Error) => {
      console.error("Assistant transport error:", error);
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <GraphToolUI />
      {children ?? (
        <div className="h-dvh">
          <Thread />
        </div>
      )}
    </AssistantRuntimeProvider>
  );
}
