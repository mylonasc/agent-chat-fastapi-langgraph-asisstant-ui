import {
  AssistantTransportConnectionMetadata,
  unstable_createMessageConverter as createMessageConverter,
} from "@assistant-ui/react";

import {
  convertLangChainMessages,
  LangChainMessage,
} from "@assistant-ui/react-langgraph";

const LangChainMessageConverter = createMessageConverter(
  convertLangChainMessages,
);

type State = {
  messages: LangChainMessage[];
  thread_id?: string;
  user_id?: string;
};

export const converter = (
  state: State | undefined,
  connectionMetadata: AssistantTransportConnectionMetadata,
) => {
  const serverMessages = state?.messages ?? [];
  const isSending = connectionMetadata.isSending;

  const pendingHumanMessages = connectionMetadata.pendingCommands
    .filter((cmd) => cmd.type === "add-message")
    .map((cmd) => ({
      type: "human" as const,
      content: cmd.message.parts
        .map((p) => (p.type === "text" ? p.text : ""))
        .join(""),
    }));

  const hasHumanInServer = serverMessages.some((m: any) => m.type === "human");
  const allMessages =
    isSending && !hasHumanInServer
      ? [...pendingHumanMessages, ...serverMessages]
      : serverMessages;
  const threadMessages = LangChainMessageConverter.toThreadMessages(
    allMessages,
  ).map((message, index) => ({
    ...message,
    // Prefer the source LangChain ID even if a converter omits it. This keeps
    // stored UI rows, feedback targets, and hydration stable across reloads.
    id:
      message.id ||
      String((allMessages[index] as { id?: string } | undefined)?.id ?? `legacy-${index}`),
  }));

  return {
    // Stable logical IDs keep incremental repository updates in transcript order.
    messages: threadMessages,
    isRunning: isSending,
  };
};

// export const converter = (state: State, connectionMetadata: AssistantTransportConnectionMetadata) => {
//   const serverMessages = state.messages || [];
//   const isSending = connectionMetadata.isSending;

//   const pendingHumanMessages = connectionMetadata.pendingCommands
//     .filter((cmd) => cmd.type === "add-message")
//     .map((cmd) => ({
//       id: cmd.message.id,
//       type: "human" as const,
//       content: [{
//         type: "text" as const,
//         text: cmd.message.parts.map(p => p.type === 'text' ? p.text : '').join("")
//       }],
//     }));

//   const hasHumanInServer = serverMessages.some((m) => m.type === "human");
//   const allMessages = isSending && !hasHumanInServer ? [...pendingHumanMessages, ...serverMessages] : serverMessages;

//   return {
//     messages: LangChainMessageConverter.toThreadMessages(allMessages),
//     isRunning: isSending,
//   };
// };
