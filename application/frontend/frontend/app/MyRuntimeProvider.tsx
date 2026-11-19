"use client";

import React, { ReactNode, useEffect, useMemo, useState } from "react";
import {
  AssistantRuntimeProvider,
  ExportedMessageRepository,
  useAssistantState,
  useAssistantTransportRuntime,
  useLocalRuntime,
  useThreadListItem,
} from "@assistant-ui/react";

import { createPackagedChatAdapter } from "./packaged-chat-adapter";
import { useApiClient } from "@/hooks/use-api-client";
import type { ApiClient } from "@/lib/api-client";
import {
  createChatMessageConverter,
  type ChatTransportMessage,
} from "@/lib/assistant/converter";
import { createRemoteThreadListAdapter } from "@/lib/assistant/remote-thread-list-adapter";
import { useRemoteThreadListRuntime } from "@/lib/assistant/runtime-compat";

const converter = createChatMessageConverter({
  syntheticIdPrefix: "legacy-",
  optimisticHumans: "while-sending",
  hydrateStoredUiTranscript: true,
});

// ------------------------------------------------------------------
// RUNTIME HOOK
// ------------------------------------------------------------------
function usePerThreadRuntime() {
  const item = useThreadListItem();
  const { config, client, loaded } = useApiClient();
  const backendThreadId = item.remoteId ?? item.id;
  // Never touch the backend before the deployment config resolves: the
  // pre-load client points at the build-time fallback base, and a foreign
  // server there happily answers message fetches (even with 200s), which
  // would poison hydration and transcript sync with the wrong backend.
  // Threads already imported in this mount must not be re-imported: runtime
  // or client identity churn would otherwise clobber fresh turns with the
  // stale fetch that triggered this effect.
  const importedForRef = React.useRef<string | null>(null);
  // Live UI message count (mirrored into a ref for the async import below).
  const messageCount = useAssistantState((s) => s.thread.messages.length);
  const messageCountRef = React.useRef(messageCount);
  useEffect(() => {
    messageCountRef.current = messageCount;
  }, [messageCount]);

  // LocalRuntime owns message branches and edit/reload commands. The adapter
  // sends only the selected branch to the packaged transport endpoint.
  const adapter = useMemo(
    () => createPackagedChatAdapter(client, backendThreadId),
    [backendThreadId, client],
  );
  const runtime = useLocalRuntime(adapter);

  useEffect(() => {
    // Capability-gated: a deployment without transcript storage serves no
    // message endpoint, so hydration must not request one.
    if (!loaded || !config.features.transcripts) return;
    const remoteId = item.remoteId;
    if (!remoteId || importedForRef.current === remoteId) return;

    let isMounted = true;

    const fetchAndImport = async () => {
      try {
        const data = await client.transcripts.list(remoteId);
        const incoming = converter(
          { messages: data.messages as ChatTransportMessage[] },
          { isSending: false, pendingCommands: [], toolStatuses: {} },
        ).messages;

        if (!isMounted) return;
        importedForRef.current = remoteId;

        // Only hydrate an empty runtime. Comparing all stored branch rows with
        // the selected branch length would mistake valid alternatives for new
        // local turns and can create phantom branches.
        if (messageCountRef.current > 0) return;
        try {
          const repository = ExportedMessageRepository.fromArray(incoming);
          runtime.thread.import({
            messages: repository.messages.map(({ message, parentId }) => ({
              message,
              parentId: Object.hasOwn(
                message.metadata?.custom ?? {},
                "branchParentId",
              )
                ? (message.metadata.custom.branchParentId as string | null)
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
    return () => {
      isMounted = false;
    };
  }, [item.remoteId, runtime, client, config.features.transcripts, loaded]);

  return runtime;
}

// ------------------------------------------------------------------
// PROVIDERS
// ------------------------------------------------------------------
function ProviderInner({ children }: { children: ReactNode }) {
  // Gate the whole runtime on the loaded deployment config. The thread-list
  // runtime fires its (cached, never-refreshed) initial load on mount. Wait
  // for the shared application-services provider to resolve deployment
  // configuration before constructing it.
  const { client, loaded } = useApiClient();
  if (!loaded) {
    return (
      <main className="flex h-dvh items-center justify-center text-sm text-muted-foreground">
        Loading chat configuration…
      </main>
    );
  }
  return <ProviderRuntime client={client}>{children}</ProviderRuntime>;
}

function ProviderRuntime({
  children,
  client,
}: {
  children: ReactNode;
  client: ApiClient;
}) {
  const { config } = useApiClient();
  if (!config.features.threads) {
    return (
      <SingleThreadRuntime client={client}>{children}</SingleThreadRuntime>
    );
  }
  return <ThreadListRuntime client={client}>{children}</ThreadListRuntime>;
}

/** Threadless deployment: one transport-backed conversation, no list. */
function SingleThreadRuntime({
  children,
  client,
}: {
  children: ReactNode;
  client: ApiClient;
}) {
  const runtime = useAssistantTransportRuntime({
    initialState: { messages: [] },
    api: client.assistantUrl(),
    headers: client.headers(),
    converter,
    onError: (error: Error) => {
      console.error("Assistant transport error:", error);
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}

function ThreadListRuntime({
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
  const adapter = useMemo(
    () =>
      createRemoteThreadListAdapter({
        getClient: () => clientRef.current,
        onError: (message) => setApiError(message),
      }),
    [],
  );

  const runtime = useRemoteThreadListRuntime({
    adapter,
    runtimeHook: usePerThreadRuntime,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {apiError && (
        <div
          role="alert"
          className="fixed right-4 bottom-4 z-50 rounded border bg-background p-3 text-sm shadow"
        >
          {apiError}
          <button className="ml-3 underline" onClick={() => setApiError(null)}>
            Dismiss
          </button>
        </div>
      )}
      {children}
    </AssistantRuntimeProvider>
  );
}

export default function MyRuntimeProvider({
  children,
}: {
  children: ReactNode;
}) {
  return <ProviderInner>{children}</ProviderInner>;
}
