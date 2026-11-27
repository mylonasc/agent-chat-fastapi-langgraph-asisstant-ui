"use client";

import {
  AssistantRuntimeProvider,
  useAssistantTransportRuntime,
} from "@assistant-ui/react";
import { ReactNode } from "react";

import { Thread } from "@/components/assistant-ui/thread";
import { useApiClient } from "@/hooks/use-api-client";
import { createChatMessageConverter } from "@/lib/assistant/converter";
import MyRuntimeProvider from "./MyRuntimeProvider";

const converter = createChatMessageConverter({
  syntheticIdPrefix: "m-",
  optimisticHumans: "until-echoed",
  hydrateStoredUiTranscript: false,
});

/**
 * Minimal preset: single-thread chat without thread-list/admin chrome.
 * The shared Thread view is reused; only the runtime composition differs.
 */
export function MinimalAssistant({ children }: { children?: ReactNode }) {
  const { config } = useApiClient();
  return config.tooling?.enabled ? (
    <MyRuntimeProvider>
      {children ?? (
        <main className="h-dvh">
          <Thread />
        </main>
      )}
    </MyRuntimeProvider>
  ) : (
    <LegacyMinimalAssistant>{children}</LegacyMinimalAssistant>
  );
}

function LegacyMinimalAssistant({ children }: { children?: ReactNode }) {
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
      {children ?? (
        <main className="h-dvh">
          <Thread />
        </main>
      )}
    </AssistantRuntimeProvider>
  );
}
