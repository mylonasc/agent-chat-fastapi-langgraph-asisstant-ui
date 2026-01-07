"use client";

import React, { ReactNode, useEffect, useMemo } from "react";
import {
  AssistantRuntimeProvider,
  unstable_useRemoteThreadListRuntime as useRemoteThreadListRuntime,
  useAssistantTransportRuntime,
  useThreadListItem,
} from "@assistant-ui/react";

import { converter } from "./MyMessageConverter";

const API_BASE = "http://localhost:8010";

const debugLog = (label: string, ...data: any[]) => {
  console.log(
    `%c[${label}]`,
    "background: #007acc; color: white; padding: 2px 4px; border-radius: 2px;",
    ...data
  );
};

// ------------------------------------------------------------------
// HELPER: Sanitizes AND Links Messages
// ------------------------------------------------------------------
// const mapBackendMessageToUi = (msg: any, previousId: string | null) => {
//   // 1. Map Role
//   let role = "user";
//   if (msg.type === "human" || msg.role === "user") role = "user";
//   else if (msg.type === "ai" || msg.role === "assistant") role = "assistant";
//   else if (msg.type === "system" || msg.role === "system") role = "system";

//   // 2. Strict ID Coercion
//   const id = msg.id ? String(msg.id) : Math.random().toString(36).slice(2);

//   // 3. Normalize Content
//   let content = msg.content;
//   if (typeof content === "string") {
//     content = [{ type: "text", text: content }];
//   } else if (Array.isArray(content)) {
//     content = content.map((part: any) => ({
//       type: part.type ?? "text",
//       text: String(part.text ?? ""),
//     }));
//   } else {
//     content = [{ type: "text", text: "" }];
//   }

//   return {
//     id,
//     role,
//     content,
//     // createdAt: msg.created_at ? new Date(msg.created_at) : new Date(),
//     // parentId: previousId, 
//   };
// };

// ------------------------------------------------------------------
// RUNTIME HOOK
// ------------------------------------------------------------------
function usePerThreadTransportRuntime() {
  const item = useThreadListItem();
  const backendThreadId = item.remoteId ?? item.id;

  // Memoize config to prevent runtime recreation on re-renders
  const runtimeConfig = useMemo(() => ({
    api: `${API_BASE}/assistant`,
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
        debugLog("Hydration:Start", `Fetching ${item.remoteId}`);
        const res = await fetch(`${API_BASE}/threads/${item.remoteId}/messages`);
        const data = await res.json();

        if (!isMounted || !data.messages) return;

        // --- STEP 1: Process Linear History ---
        // const cleanMessages = [];
        // let lastId = null;

        // for (const rawMsg of data.messages) {
        //   //  const cleanMsg = mapBackendMessageToUi(rawMsg, lastId);
        //    cleanMessages.push(cleanMsg);
        //   //  lastId = cleanMsg.id; // Set current ID as parent for next msg
        // }

        // --- STEP 2: Import ---
        const threadRuntime = (runtime as any).thread;
        if (threadRuntime?.import) {
          try {
            console.log('---');
            console.log(data.messages);
            
            const threadRuntime = (runtime as any).thread;

            console.log("[Hydration] fetched", data.messages?.length, data.messages?.[0]);

            threadRuntime.unstable_loadExternalState({
              thread_id: backendThreadId,
              user_id: "default_user",
              messages: data.messages ?? [],
            });

            console.log("[Hydration] transport state after load", (runtime as any).thread?.getState?.());

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
          const res = await fetch(`${API_BASE}/threads?user_id=default_user`);
          const data = await res.json();
          return {
            threads: (data || []).map((t: any) => ({
              remoteId: t.id,
              title: t.title || "New Chat",
              status: "regular" as const,
            })),
          };
        } catch (e) { return { threads: [] }; }
      },
      async fetch(threadId: string) {
        const res = await fetch(`${API_BASE}/threads/${threadId}`);
        const data = await res.json();
        return { remoteId: data.id, title: data.title, status: "regular" as const };
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
      async generateTitle() { return "New Chat"; },
      async rename(threadId: string, newTitle: string) { return { title: newTitle }; },
      async archive() {},
      async delete() {},
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