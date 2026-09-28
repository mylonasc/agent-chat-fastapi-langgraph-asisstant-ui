"use client";

import React, { ReactNode, useEffect, useMemo } from "react";
import type { AssistantStreamChunk } from "assistant-stream";
import {
  AssistantRuntimeProvider,
  unstable_useRemoteThreadListRuntime as useRemoteThreadListRuntime,
  useAssistantTransportRuntime,
  useThreadListItem,
} from "@assistant-ui/react";

import { converter } from "./MyMessageConverter";
import { useApiClient } from "@/hooks/use-api-client";

// ------------------------------------------------------------------
// RUNTIME HOOK
// ------------------------------------------------------------------
function usePerThreadTransportRuntime() {
  const item = useThreadListItem();
  const backendThreadId = item.remoteId ?? item.id;
  const { client } = useApiClient();

  // Memoize config to prevent runtime recreation on re-renders
  const runtimeConfig = useMemo(() => ({
    api: client.assistantUrl(),
    headers: client.headers(),
    converter,
    initialState: {
      messages: [],
      thread_id: backendThreadId,
    },
  }), [backendThreadId, client]);

  const runtime = useAssistantTransportRuntime(runtimeConfig);

  useEffect(() => {
    const remoteId = item.remoteId;
    if (!remoteId) return;

    // Skip if messages already exist in state
    const threadState = (runtime as any).thread?.getState?.();
    if (threadState?.messages && threadState.messages.length > 0) return;

    let isMounted = true;

    const fetchAndImport = async () => {
      try {
        const data = await client.getMessages(remoteId);

        if (!isMounted || !data.messages) return;

        const threadRuntime = (runtime as any).thread;
        if (threadRuntime?.unstable_loadExternalState) {
          try {
            threadRuntime.unstable_loadExternalState({
              thread_id: backendThreadId,
              messages: data.messages ?? [],
            });
          } catch (importErr) {
             console.error("[Hydration:CRASH]", importErr);
             // This catch block prevents the entire app from white-screening
          }
        }
      } catch (e) {
        if (isMounted) console.error("[Hydration:NetworkError]", e);
      }
    };

    fetchAndImport();
    return () => { isMounted = false; };
  }, [item.remoteId, runtime, client]);

  return runtime;
}

// ------------------------------------------------------------------
// PROVIDER
// ------------------------------------------------------------------
function ProviderInner({ children }: { children: ReactNode }) {
  const { client } = useApiClient();
  const adapter = useMemo(() => ({
      async list() {
        try {
          const data = await client.listThreads();
          return {
            threads: (data || []).map((t: any) => ({
              remoteId: t.id,
              title: t.title || "New Chat",
              status: t.is_archived ? ("archived" as const) : ("regular" as const),
            })),
          };
        } catch (e) { return { threads: [] }; }
      },
      async fetch(threadId: string) {
        const data = await client.getThread(threadId);
        return {
          remoteId: data.id,
          title: data.title,
          status: data.is_archived ? ("archived" as const) : ("regular" as const),
        };
      },
      async initialize(localId: string) {
        const data = await client.createThread(localId);
        return { remoteId: data.id };
      },
      async generateTitle() {
        return new ReadableStream<AssistantStreamChunk>();
      },
      async rename(threadId: string, newTitle: string) {
        await client.renameThread(threadId, newTitle);
      },
      async archive(threadId: string) {
        await client.archiveThread(threadId, true);
      },
      async unarchive(threadId: string) {
        await client.archiveThread(threadId, false);
      },
      async delete(threadId: string) {
        await client.deleteThread(threadId);
      },
    }), [client]);

  const runtime = useRemoteThreadListRuntime({
    adapter: adapter as any, 
    runtimeHook: usePerThreadTransportRuntime,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}

export default function MyRuntimeProvider({ children }: { children: ReactNode }) {
  return <ProviderInner>{children}</ProviderInner>;
}
