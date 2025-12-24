import { 
    AssistantTransportConnectionMetadata,
    unstable_createMessageConverter as createMessageConverter, 


 } from '@assistant-ui/react'

import {
  convertLangChainMessages,
  LangChainMessage,
} from "@assistant-ui/react-langgraph";

const LangChainMessageConverter = createMessageConverter(convertLangChainMessages);


export const converter = (
  state: State | undefined,
  connectionMetadata: AssistantTransportConnectionMetadata
) => {
  const serverMessages = state?.messages ?? [];
  const isSending = connectionMetadata.isSending;

  const pendingHumanMessages = connectionMetadata.pendingCommands
    .filter((cmd) => cmd.type === "add-message")
    .map((cmd) => ({
      id: cmd.message.id,
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

  const hasHumanInServer = serverMessages.some((m: any) => m.type === "human");
  const allMessages =
    isSending && !hasHumanInServer
      ? [...pendingHumanMessages, ...serverMessages]
      : serverMessages;

  return {
    messages: LangChainMessageConverter.toThreadMessages(allMessages),
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
