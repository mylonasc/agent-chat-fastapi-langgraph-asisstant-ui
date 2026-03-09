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

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/assistant$/, "") ??
  "http://localhost:8010";

// ------------------------------------------------------------------
// RUNTIME HOOK
// ------------------------------------------------------------------
function usePerThreadTransportRuntime() {
  const item = useThreadListItem();
  const backendThreadId = item.remoteId ?? item.id;

  // Memoize config to prevent runtime recreation on re-renders
  const runtimeConfig = useMemo(() => ({
    api: `${API_BASE}/assistant`,
    headers: {},
    converter,
    initialState: {
      thread_id: backendThreadId,
      user_id: "default_user",
    },
  }), [backendThreadId]);

  const runtime = useAssistantTransportRuntime(runtimeConfig);

  useEffect(() => {
    if (!item.remoteId) return;

    // Skip if messages already exist in state
    const threadState = (runtime as any).thread?.getState?.();
    if (threadState?.messages && threadState.messages.length > 0) return;

    let isMounted = true;

    const fetchAndImport = async () => {
      try {
        const res = await fetch(`${API_BASE}/threads/${item.remoteId}/messages`, {
          cache: "no-store",
        });
        const data = await res.json();

        if (!isMounted || !data.messages) return;

        const threadRuntime = (runtime as any).thread;
        if (threadRuntime?.unstable_loadExternalState) {
          try {
            threadRuntime.unstable_loadExternalState({
              thread_id: backendThreadId,
              user_id: "default_user",
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
  }, [item.remoteId, runtime]);

  return runtime;
}

// ------------------------------------------------------------------
// PROVIDER
// ------------------------------------------------------------------
function ProviderInner({ children }: { children: ReactNode }) {
  const adapter = useMemo(() => ({
      async list() {
        try {
          const res = await fetch(`${API_BASE}/threads?user_id=default_user`, {
            cache: "no-store",
          });
          const data = await res.json();
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
        const res = await fetch(`${API_BASE}/threads/${threadId}`, { cache: "no-store" });
        const data = await res.json();
        return {
          remoteId: data.id,
          title: data.title,
          status: data.is_archived ? ("archived" as const) : ("regular" as const),
        };
      },
      async initialize(localId: string) {
        const res = await fetch(`${API_BASE}/threads`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ localId, user_id: "default_user", title: "New Chat" }),
        });
        const data = await res.json();
        return { remoteId: data.id };
      },
      async generateTitle() {
        return new ReadableStream<AssistantStreamChunk>();
      },
      async rename(threadId: string, newTitle: string) {
        const res = await fetch(`${API_BASE}/threads/${threadId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: newTitle }),
        });
        if (!res.ok) throw new Error("Failed to rename thread");
      },
      async archive(threadId: string) {
        const res = await fetch(`${API_BASE}/threads/${threadId}/archive`, {
          method: "POST",
        });
        if (!res.ok) throw new Error("Failed to archive thread");
      },
      async unarchive(threadId: string) {
        const res = await fetch(`${API_BASE}/threads/${threadId}/unarchive`, {
          method: "POST",
        });
        if (!res.ok) throw new Error("Failed to unarchive thread");
      },
      async delete(threadId: string) {
        const res = await fetch(`${API_BASE}/threads/${threadId}`, {
          method: "DELETE",
        });
        if (!res.ok) throw new Error("Failed to delete thread");
      },
    }), []);

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
