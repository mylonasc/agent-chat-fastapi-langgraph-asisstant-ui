"use client";

import {
  useAssistantApi,
  useAssistantState,
  type ThreadMessage,
} from "@assistant-ui/react";
import { useEffect, type FC } from "react";

import { useApiClient } from "@/hooks/use-api-client";
import { ApiError } from "@/lib/api-client";

import { useThreadSyncStore } from "./thread-sync-store";

/** Persist only completed turns; stable message IDs make retries idempotent. */
export const TranscriptSynchronizer: FC = () => {
  const api = useAssistantApi();
  // Gated on loaded: pre-config appends would land on the build-time
  // fallback base instead of the deployment backend.
  const { config, client, identity, loaded } = useApiClient();
  const store = useThreadSyncStore();
  const threadItem = useAssistantState((state) => state.threadListItem);
  const messages = useAssistantState((state) => state.thread.messages);
  const isRunning = useAssistantState((state) => state.thread.isRunning);

  useEffect(() => {
    // Capability-gated: a deployment without transcript storage must not
    // append messages, and a threadless runtime only has a local
    // `__LOCALID_` thread that the backend never created.
    if (!loaded || !config.features.threads || !config.features.transcripts) {
      return;
    }
    const threadId = threadItem?.remoteId;
    if (!threadId || messages.length === 0) return;
    const syncedPayloads = store.getSyncedPayloads(
      `${identity.subject ?? ""}::${threadId}`,
    );
    // Export the complete repository, not only the selected branch. Parent
    // links preserve edited/regenerated alternatives across hydration.
    const messagesToSync = api
      .thread()
      .export()
      .messages.filter(
        ({ message }) =>
          message.role !== "assistant" || message.status.type !== "running",
      )
      .map(
        ({ message, parentId }) =>
          ({
            ...message,
            metadata: {
              ...message.metadata,
              custom: {
                ...message.metadata.custom,
                branchParentId: parentId,
              },
            },
          }) as ThreadMessage,
      );
    if (messagesToSync.length === 0) return;

    // Assistant UI can publish a final state immediately after isRunning flips.
    // Wait for that burst to settle before storing an immutable transcript row.
    const timer = window.setTimeout(() => {
      void (async () => {
        for (const message of messagesToSync) {
          if (message.id == null) continue;
          const payload = JSON.stringify(message);
          if (syncedPayloads.get(message.id) === payload) continue;
          try {
            await client.transcripts.append(threadId, message);
          } catch (error) {
            // 409 means the server already stores this id: the durability
            // goal is met, so record it instead of retrying forever.
            const status =
              error instanceof ApiError
                ? error.status
                : (error as { status?: unknown })?.status;
            if (status !== 409) throw error;
          }
          syncedPayloads.set(message.id, payload);
        }
      })().catch(() => {
        // The next completed turn retries unchanged message IDs without duplicates.
      });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [
    api,
    client,
    config.features.threads,
    config.features.transcripts,
    identity.subject,
    isRunning,
    loaded,
    messages,
    store,
    threadItem?.id,
    threadItem?.remoteId,
  ]);

  return null;
};
