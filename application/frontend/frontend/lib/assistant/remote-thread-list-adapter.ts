/**
 * Remote thread-list adapter wiring.
 *
 * This module owns the mapping between backend thread DTOs and assistant-ui's
 * remote thread-list contract. Keeping it outside the React provider makes the
 * adapter independently testable and keeps the provider focused on runtime
 * composition.
 */
import type { AssistantStreamChunk } from "assistant-stream";

import type { ApiClient } from "@/lib/api-client";
import type { ThreadMetadata } from "@/lib/api/types";

import type {
  RemoteThreadListAdapter,
  RemoteThreadMetadata,
} from "./runtime-compat";

export type RemoteThreadListAdapterOptions = {
  /** Late-bound client so the cached adapter always uses the live instance. */
  getClient: () => ApiClient;
  /** Surface list failures without throwing into the thread-list runtime. */
  onError?: (message: string) => void;
};

function toRemoteThreadMetadata(thread: ThreadMetadata): RemoteThreadMetadata {
  return {
    remoteId: thread.id,
    title: thread.title || "New Chat",
    status: thread.is_archived ? "archived" : "regular",
  };
}

export function createRemoteThreadListAdapter({
  getClient,
  onError,
}: RemoteThreadListAdapterOptions): RemoteThreadListAdapter {
  return {
    async list() {
      try {
        const threads = await getClient().threads.list();
        return { threads: threads.map(toRemoteThreadMetadata) };
      } catch (error) {
        onError?.(
          error instanceof Error ? error.message : "Unable to load chats",
        );
        return { threads: [] };
      }
    },

    async fetch(threadId) {
      return toRemoteThreadMetadata(await getClient().threads.get(threadId));
    },

    async initialize(localId) {
      const thread = await getClient().threads.create(localId);
      return { remoteId: thread.id, externalId: undefined };
    },

    async generateTitle() {
      // The backend titles threads on first response; the adapter never
      // generates titles itself.
      return new ReadableStream<AssistantStreamChunk>();
    },

    async rename(threadId, newTitle) {
      await getClient().threads.rename(threadId, newTitle);
    },

    async archive(threadId) {
      await getClient().threads.setArchived(threadId, true);
    },

    async unarchive(threadId) {
      await getClient().threads.setArchived(threadId, false);
    },

    async delete(threadId) {
      await getClient().threads.delete(threadId);
    },
  };
}
