"use client";

import React, { ReactNode, useEffect, useMemo, useRef } from "react";
import {
  AssistantRuntimeProvider,
  RuntimeAdapterProvider,
  unstable_useRemoteThreadListRuntime as useRemoteThreadListRuntime,
  useAssistantApi,
  useAssistantRuntime,
  useAssistantState,
  useThreadListItem,
  useAssistantTransportRuntime,
  type ThreadHistoryAdapter,
} from "@assistant-ui/react";

import { converter } from "./MyMessageConverter";

const API_BASE = "http://localhost:8010";
const DEBUG = true;

function log(...args: any[]) {
  if (!DEBUG) return;
  console.log(...args);
}
function warn(...args: any[]) {
  if (!DEBUG) return;
  console.warn(...args);
}
function err(...args: any[]) {
  if (!DEBUG) return;
  console.error(...args);
}

console.log("[MyRuntimeProvider] module evaluated");

function usePerThreadTransportRuntime() {
  const item = useThreadListItem() as any;
  const backendThreadId = item?.remoteId ?? item?.id ?? "new";

  useEffect(() => {
    log("[runtimeHook] mounted", {
      id: item?.id,
      remoteId: item?.remoteId,
      backendThreadId,
      title: item?.title,
    });
  }, [item?.id, item?.remoteId, item?.title, backendThreadId]);

  return useAssistantTransportRuntime({
    api: `${API_BASE}/assistant`,
    converter,
    initialState: {
      thread_id: backendThreadId,
      user_id: "default_user",
      messages: [],
    },
  });
}

function AutoSelectLogic() {
  const runtime = useAssistantRuntime();
  const threadsStore = useAssistantState((s) => (s as any).threads ?? null);

  const mainThreadId: string | undefined = threadsStore?.mainThreadId;
  const threadIds: string[] = Array.isArray(threadsStore?.threadIds) ? threadsStore.threadIds : [];

  const didAutoSelect = useRef(false);

  useEffect(() => {
    log("[AutoSelectLogic] effect", { mainThreadId, threadIds, didAutoSelect: didAutoSelect.current });

    if (!runtime) return;
    if (!threadIds.length) return;

    if (mainThreadId && threadIds.includes(mainThreadId)) return;
    if (didAutoSelect.current) return;

    didAutoSelect.current = true;
    const target = threadIds[0];
    log("[AutoSelectLogic] bootstrap switching to:", target);

    try {
      (runtime as any).switchToThread?.(target);
    } catch (e) {
      err("[AutoSelectLogic] switchToThread failed:", e);
    }
  }, [runtime, mainThreadId, JSON.stringify(threadIds)]);

  return null;
}

function ProviderInner({ children }: { children: ReactNode }) {
  const adapter = useMemo(
    () => ({
      async list() {
        log("[ThreadListAdapter.list] GET /threads");
        const res = await fetch(`${API_BASE}/threads?user_id=default_user`, { cache: "no-store" });
        const data = await res.json();
        log("[ThreadListAdapter.list] received:", data);

        return {
          threads: (data || []).map((t: any) => ({
            remoteId: t.id,
            title: t.title,
            status: "regular",
          })),
        };
      },

      async initialize(localId: string) {
        log("[ThreadListAdapter.initialize] POST /threads localId:", localId);
        const res = await fetch(`${API_BASE}/threads`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ localId, user_id: "default_user", title: "New Chat" }),
        });
        const data = await res.json();
        log("[ThreadListAdapter.initialize] response:", data);
        return { remoteId: data.id };
      },

      unstable_Provider: ({ children }: { children: ReactNode }) => {
        const api = useAssistantApi();
        log("[unstable_Provider] render (per-thread scope)");

        const history: ThreadHistoryAdapter = useMemo(() => {
          log("[history adapter] created (per-thread scope)");

          return {
            async load() {
              const itemApi: any = api.threadListItem();
              const init = await itemApi.initialize();
              const remoteId = init?.remoteId;

              log("[history.load] called", { init });

              if (!remoteId) return { messages: [] };

              const url = `${API_BASE}/threads/${remoteId}/messages`;
              log("[history.load] GET", url);

              const res = await fetch(url, { cache: "no-store" });
              const data = await res.json();

              const msgs = Array.isArray(data?.messages) ? data.messages : [];
              log("[history.load] received", {
                len: msgs.length,
                firstKeys: msgs[0] ? Object.keys(msgs[0]) : null,
              });

              return { messages: msgs };
            },

            async append(message) {
              const itemApi: any = api.threadListItem();
              const init = await itemApi.initialize();
              const remoteId = init?.remoteId;

              log("[history.append] called", {
                remoteId,
                id: (message as any)?.id,
                role: (message as any)?.role,
              });

              if (!remoteId) return;

              await fetch(`${API_BASE}/threads/${remoteId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message }),
              });
            },
          };
        }, [api]);

        return <RuntimeAdapterProvider adapters={{ history }}>{children}</RuntimeAdapterProvider>;
      },
    }),
    []
  );

  const runtime = useRemoteThreadListRuntime({
    adapter: adapter as any,
    runtimeHook: usePerThreadTransportRuntime,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AutoSelectLogic />
      {children}
    </AssistantRuntimeProvider>
  );
}

/**
 * ✅ Default export so imports never break due to named export mismatch.
 */
export default function MyRuntimeProvider({ children }: { children: ReactNode }) {
  return <ProviderInner>{children}</ProviderInner>;
}
