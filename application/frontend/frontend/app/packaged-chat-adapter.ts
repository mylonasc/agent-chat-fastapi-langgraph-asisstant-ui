import type { ChatModelAdapter, ThreadMessage } from "@assistant-ui/react";
import {
  AssistantMessageAccumulator,
  DataStreamDecoder,
  unstable_createInitialMessage as createInitialMessage,
} from "assistant-stream";
import { asAsyncIterableStream } from "assistant-stream/utils";
import type { ApiClient } from "@/lib/api-client";
import { setRunError } from "@/lib/run-errors";
import { converter } from "./MyMessageConverter";

// Keep the graph's rich assistant/tool messages for subsequent turns. Hydrated
// transcripts without this metadata still work for ordinary text conversations.
function toGraphMessages(message: ThreadMessage): any[] {
  const original = message.metadata?.custom?.graphMessages;
  if (Array.isArray(original)) return original;
  return [
    {
      id: message.id,
      type:
        message.role === "user"
          ? "human"
          : message.role === "assistant"
            ? "ai"
            : "system",
      content: message.content
        .map((part) => {
          if (part.type === "text") return { type: "text", text: part.text };
          if (part.type === "image")
            return { type: "image_url", image_url: { url: part.image } };
          return null;
        })
        .filter(Boolean),
    },
  ];
}

/** LocalRuntime owns message identity and branches; the packaged API owns inference. */
export function createPackagedChatAdapter(
  client: ApiClient,
  threadId: string,
): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      // LocalRuntime supplies only the selected branch, truncated at the edited
      // prompt / regenerated answer. Never send abandoned alternatives as history.
      const graphMessages = messages.flatMap(toGraphMessages);
      const prompt = messages.at(-1);
      const hasPrompt = prompt?.role === "user";
      try {
        const response = await fetch(client.assistantUrl(), {
          method: "POST",
          headers: client.headers({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            commands: hasPrompt
              ? [
                  {
                    type: "add-message",
                    message: {
                      id: prompt.id,
                      role: "user",
                      parts: prompt.content,
                    },
                  },
                ]
              : [],
            state: {
              messages: hasPrompt ? graphMessages.slice(0, -1) : graphMessages,
              thread_id: threadId,
            },
          }),
          signal: abortSignal,
        });
        if (!response.ok)
          throw new Error(
            `Status ${response.status}: ${await response.text()}`,
          );
        if (!response.body) throw new Error("Response body is null");
        let streamError: string | undefined;
        const stream = response.body
          .pipeThrough(new DataStreamDecoder())
          .pipeThrough(
            new AssistantMessageAccumulator({
              initialMessage: createInitialMessage(),
              onError: (error) => {
                streamError = error;
              },
            }),
          );
        for await (const chunk of asAsyncIterableStream(stream)) {
          const state = chunk.metadata.unstable_state as
            | { messages: any[] }
            | undefined;
          if (!state?.messages) continue;
          const converted = converter(state, {
            isSending: true,
            pendingCommands: [],
            toolStatuses: {},
          });
          const answer = converted.messages.findLast(
            (message) => message.role === "assistant",
          );
          // The first state update may contain only the prompt/history.
          const generated = state.messages.slice(graphMessages.length);
          if (!answer || generated.length === 0) continue;
          yield {
            content: answer.content,
            metadata: { custom: { graphMessages: generated } },
          };
        }
        if (streamError) throw new Error(streamError);
      } catch (error) {
        if (!abortSignal.aborted) {
          setRunError(threadId, {
            text: error instanceof Error ? error.message : String(error),
            userText:
              messages
                .findLast((message) => message.role === "user")
                ?.content.map((part) => (part.type === "text" ? part.text : ""))
                .join("") ?? "",
          });
        }
        // LocalRuntime rethrows adapter exceptions from its event handler.
        // Surface failures through the existing per-thread alert and message
        // status instead of producing an unhandled browser rejection.
        yield {
          status: {
            type: "incomplete",
            reason: abortSignal.aborted ? "cancelled" : "error",
          },
        };
      }
    },
  };
}
