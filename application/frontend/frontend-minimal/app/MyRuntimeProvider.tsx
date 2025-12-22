"use client";

import {
  AssistantRuntimeProvider,
  AssistantTransportConnectionMetadata,
  makeAssistantTool,
  unstable_createMessageConverter as createMessageConverter,
  useAssistantTransportRuntime,
} from "@assistant-ui/react";
import {
  convertLangChainMessages,
  LangChainMessage,
} from "@assistant-ui/react-langgraph";
import { ReactNode } from "react";
import { z } from "zod";

// // Frontend tool with execute function
// const WeatherTool = makeAssistantTool({
//   type: "frontend",
//   toolName: "get_weather",
//   description: "Get the current weather for a city",
//   parameters: z.object({
//     location: z.string().describe("The city to get weather for"),
//     unit: z
//       .enum(["celsius", "fahrenheit"])
//       .optional()
//       .describe("Temperature unit"),
//   }),
//   execute: async ({ location, unit = "celsius" }) => {
//     console.log(`Getting weather for ${location} in ${unit}`);
//     // Simulate API call
//     await new Promise((resolve) => setTimeout(resolve, 1000));

//     const temp = Math.floor(Math.random() * 30) + 10;
//     const conditions = ["sunny", "cloudy", "rainy", "partly cloudy"];
//     const condition = conditions[Math.floor(Math.random() * conditions.length)];

//     return {
//       location,
//       temperature: temp,
//       unit,
//       condition,
//       humidity: Math.floor(Math.random() * 40) + 40,
//       windSpeed: Math.floor(Math.random() * 20) + 5,
//     };
//   },
//   streamCall: async (reader) => {
//     console.log("streamCall", reader);
//     const city = await reader.args.get("location");
//     console.log("location", city);

//     const args = await reader.args.get();
//     console.log("args", args);

//     const result = await reader.response.get();
//     console.log("result", result);
//   },
// });

type MyRuntimeProviderProps = {
  children: ReactNode;
};

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
  
  // 1. Extract pending human messages from the transport layer
  const pendingHumanMessages = connectionMetadata.pendingCommands
    .filter((cmd) => cmd.type === "add-message")
    .map((cmd) => ({
      id: cmd.message.id,
      type: "human" as const,
      content: [
        {
          type: "text" as const,
          // Extract text from the parts array
          text: cmd.message.parts
            .map((p) => (p.type === "text" ? p.text : ""))
            .join(""),
        },
      ],
    }));

  // 2. Determine if the server has acknowledged the current turn.
  // We check if the server list already contains a human message.
  // Since you fixed the ID on the backend, checking for 'human' type is now reliable.
  const hasHumanInServer = serverMessages.some((m) => m.type === "human");

  // 3. Construct the combined message list.
  // If the server hasn't sent the human message back yet, we prepend the optimistic version.
  // Once the server sends it (with the ID fix), hasHumanInServer becomes true and we 
  // switch entirely to the server's ordered array.
  const allMessages = hasHumanInServer 
    ? serverMessages 
    : [...pendingHumanMessages, ...serverMessages];

  return {
    // ThreadMessages handles the specific UI layout and bubble rendering
    messages: LangChainMessageConverter.toThreadMessages(allMessages),
    isRunning: connectionMetadata.isSending,
  };
};

export function MyRuntimeProvider({ children }: MyRuntimeProviderProps) {
  const runtime = useAssistantTransportRuntime({
    initialState: {
      messages: [],
    },
    api:
      process.env["NEXT_PUBLIC_API_URL"] || "http://localhost:8010/assistant",
    converter,
    headers: async () => ({
      "Test-Header": "test-value",
    }),
    body: {
      "Test-Body": "test-value",
    },
    onResponse: () => {
      console.log("Response received from server");
    },
    onFinish: () => {
      console.log("Conversation completed");
    },
    onError: (error: Error) => {
      console.error("Assistant transport error:", error);
    },
    onCancel: () => {
      console.log("Request cancelled");
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {/* <WeatherTool /> */}

      {children}
    </AssistantRuntimeProvider>
  );
}
