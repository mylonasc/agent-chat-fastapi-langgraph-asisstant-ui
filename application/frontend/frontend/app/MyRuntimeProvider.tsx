"use client";

import React, { ReactNode, useEffect, useMemo, useState } from "react";
import type { AssistantStreamChunk } from "assistant-stream";
import {
  AssistantRuntimeProvider,
  unstable_useRemoteThreadListRuntime as useRemoteThreadListRuntime,
  useAssistantState,
  useLocalRuntime,
  useThreadListItem,
  ExportedMessageRepository,
} from "@assistant-ui/react";

import { createPackagedChatAdapter } from "./packaged-chat-adapter";
import { converter } from "./MyMessageConverter";
import type { LangChainMessage } from "@assistant-ui/react-langgraph";
import { useApiClient } from "@/hooks/use-api-client";
import type { ApiClient } from "@/lib/api-client";

// ------------------------------------------------------------------
// RUNTIME HOOK
// ------------------------------------------------------------------
function usePerThreadRuntime() {
  const item = useThreadListItem();
  const backendThreadId = item.remoteId ?? item.id;
  // Never touch the backend before the deployment config resolves: the
  // pre-load client points at the build-time fallback base, and a foreign
  // server there happily answers message fetches (even with 200s), which
  // would poison hydration and transcript sync with the wrong backend.
  const { client, loaded } = useApiClient();
  // Threads already imported in this mount must not be re-imported: runtime
  // or client identity churn would otherwise clobber fresh turns with the
  // stale fetch that triggered this effect.
  const importedForRef = React.useRef<string | null>(null);
  // Live UI message count (mirrored into a ref for the async import below).
  const messageCount = useAssistantState((s) => s.thread.messages.length);
  const messageCountRef = React.useRef(messageCount);
  messageCountRef.current = messageCount;

  const adapter = useMemo(
    () => createPackagedChatAdapter(client, backendThreadId),
    [backendThreadId, client],
  );
  const runtime = useLocalRuntime(adapter);

  useEffect(() => {
    if (!loaded) return;
    const remoteId = item.remoteId;
    if (!remoteId || importedForRef.current === remoteId) return;

    let isMounted = true;

    const fetchAndImport = async () => {
      try {
        const data = await client.getMessages(remoteId);
        // An owned thread without transcript rows can return LangChain
        // checkpoint messages. Normalize both that fallback and stored UI rows
        // before import; raw checkpoint messages have no UI role/metadata.
        const incoming = converter(
          { messages: (data.messages ?? []) as LangChainMessage[] },
          { isSending: false, pendingCommands: [], toolStatuses: {} },
        ).messages;

        if (!isMounted) return;
        importedForRef.current = remoteId;

        // Only hydrate an empty runtime. Total stored branch rows cannot be
        // compared with the length of the selected branch to detect stale data.
        if (messageCountRef.current > 0) return;
        try {
          const repository = ExportedMessageRepository.fromArray(incoming);
          runtime.thread.import({
            messages: repository.messages.map(({ message, parentId }) => ({
              message,
              parentId: Object.hasOwn(message.metadata?.custom ?? {}, "branchParentId")
                ? message.metadata.custom.branchParentId as string | null
                : parentId,
            })),
          });
        } catch (importErr) {
           console.error("[Hydration:CRASH]", importErr);
           // This catch block prevents the entire app from white-screening
        }
      } catch (e) {
        if (isMounted) console.error("[Hydration:NetworkError]", e);
      }
    };

    fetchAndImport();
    return () => { isMounted = false; };
  }, [item.remoteId, runtime, client, loaded]);

  return runtime;
}

// ------------------------------------------------------------------
// PROVIDER
// ------------------------------------------------------------------
function ProviderInner({ children }: { children: ReactNode }) {
  // Gate the whole runtime on the loaded deployment config. The thread-list
  // runtime fires its (cached, never-refreshed) initial load on mount: if
  // the adapter existed before /api/config resolves it would permanently
  // bind the build-time fallback base instead of the deployment backend.
  // NOTE: every useApiClient() instance has its own loading window, so the
  // gate is re-checked in ProviderReady with its own instance, and the
  // post-load client is passed down as a prop (never re-derived below).
  const { loaded } = useApiClient();
  if (!loaded) {
    return (
      <main className="flex h-dvh items-center justify-center text-sm text-muted-foreground">
        Loading chat configuration…
      </main>
    );
  }
  return <ProviderReady>{children}</ProviderReady>;
}

function ProviderReady({ children }: { children: ReactNode }) {
  const { client, loaded } = useApiClient();
  if (!loaded) {
    return (
      <main className="flex h-dvh items-center justify-center text-sm text-muted-foreground">
        Loading chat configuration…
      </main>
    );
  }
  // Pass the post-load client down as a prop: a fresh useApiClient() call
  // inside ProviderRuntime would start in its own loading window (build-time
  // fallback base) and the cached initial load would pin that wrong backend.
  return <ProviderRuntime client={client}>{children}</ProviderRuntime>;
}

function ProviderRuntime({
  children,
  client,
}: {
  children: ReactNode;
  client: ApiClient;
}) {
  const [apiError, setApiError] = useState<string | null>(null);
  // Late-bound client: the adapter object is created once and must always
  // call with the *current* client. Closing over the render-time client
  // would pin the build-time fallback base for the cached initial load
  // whenever this mounts during any instance's config loading window.
  const clientRef = React.useRef(client);
  clientRef.current = client;
  const adapter = useMemo(() => ({
      async list() {
        try {
          const data = await clientRef.current.listThreads();
          return {
            threads: (data || []).map((t: any) => ({
              remoteId: t.id,
              title: t.title || "New Chat",
              status: t.is_archived ? ("archived" as const) : ("regular" as const),
            })),
          };
        } catch (error) {
          setApiError(error instanceof Error ? error.message : "Unable to load chats");
          return { threads: [] };
        }
      },
      async fetch(threadId: string) {
        const data = await clientRef.current.getThread(threadId);
        return {
          remoteId: data.id,
          title: data.title,
          status: data.is_archived ? ("archived" as const) : ("regular" as const),
        };
      },
      async initialize(localId: string) {
        const data = await clientRef.current.createThread(localId);
        return { remoteId: data.id };
      },
      async generateTitle() {
        return new ReadableStream<AssistantStreamChunk>();
      },
      async rename(threadId: string, newTitle: string) {
        await clientRef.current.renameThread(threadId, newTitle);
      },
      async archive(threadId: string) {
        await clientRef.current.archiveThread(threadId, true);
      },
      async unarchive(threadId: string) {
        await clientRef.current.archiveThread(threadId, false);
      },
      async delete(threadId: string) {
        await clientRef.current.deleteThread(threadId);
      },
    }), []);

  const runtime = useRemoteThreadListRuntime({
    adapter: adapter as any, 
    runtimeHook: usePerThreadRuntime,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {apiError && (
        <div role="alert" className="fixed right-4 bottom-4 z-50 rounded border bg-background p-3 text-sm shadow">
          {apiError}
          <button className="ml-3 underline" onClick={() => setApiError(null)}>Dismiss</button>
        </div>
      )}
      {children}
    </AssistantRuntimeProvider>
  );
}

export default function MyRuntimeProvider({ children }: { children: ReactNode }) {
  return <ProviderInner>{children}</ProviderInner>;
}
