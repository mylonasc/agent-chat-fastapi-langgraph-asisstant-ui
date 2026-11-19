"use client";

import { useAssistantApi, useAssistantState } from "@assistant-ui/react";
import { useEffect, useRef, type FC } from "react";

import { useApiClient } from "@/hooks/use-api-client";

import { useThreadSyncStore } from "./thread-sync-store";

/**
 * Ensure the current thread is server-bound before allowing any send.
 *
 * In the full preset, message sync, feedback, and hydration all key off the
 * bound remote thread id. Sending before initialize() completes strands
 * turns on ids the rest of the UI never sees again.
 */
export function useEnsureThreadInitialized() {
  const { config, loaded } = useApiClient();
  const threadItem = useAssistantState((state) => state.threadListItem);
  // Block sends until the deployment config resolves: the pre-load
  // transport targets the build-time fallback base, not the backend.
  if (!loaded) {
    return { canSend: false, isInitializing: true };
  }
  if (!config.features.threads || config.ui_preset !== "full" || !threadItem) {
    return { canSend: true, isInitializing: false };
  }
  const ready = !!threadItem.remoteId;
  return { canSend: ready, isInitializing: !ready };
}

/**
 * Bind the current local thread to the server as soon as it exists.
 *
 * The thread-list runtime creates the local `__LOCALID_` entry on its own,
 * but only an explicit initialize() call creates the server session. Without
 * this, the first thread on a fresh load never gets a remoteId (binding then
 * depends on accidental list reconciliation), so syncing, feedback, and
 * hydration silently no-op while the transport happily sends elsewhere.
 *
 * Initialization waits for the initial thread list to finish loading: this
 * effect runs deeper in the tree than the runtime's own load effect, so
 * initializing first would settle its optimistic prepend into a base that
 * already lists the just-created server thread — duplicating the row.
 */
export const EnsureThreadInitialized: FC = () => {
  const api = useAssistantApi();
  const { config } = useApiClient();
  const store = useThreadSyncStore();
  const threadItem = useAssistantState((state) => state.threadListItem);
  // A transport-only runtime has no `threads` scope; default to "loaded".
  const threadsLoading = useAssistantState(
    (state) => state.threads?.isLoading ?? false,
  );
  const loadingRef = useRef(threadsLoading);
  useEffect(() => {
    loadingRef.current = threadsLoading;
  }, [threadsLoading]);

  useEffect(() => {
    // Capability-gated: a threadless deployment has no local thread item to
    // bind and must not call the thread-initialize endpoint.
    if (!config.features.threads || config.ui_preset !== "full") return;
    const localId = threadItem?.id;
    if (!localId || threadItem?.remoteId) return;
    if (store.isInitializing(localId)) return;
    let cancelled = false;
    void (async () => {
      // This effect runs deeper in the tree than the runtime's own initial
      // load, so without waiting it would initialize first and its settle
      // prepend would duplicate the row once the load lists the new thread.
      // Yield past the mount flush, then wait for the (single, cached)
      // initial load to resolve before binding.
      await new Promise((resolve) => window.setTimeout(resolve, 250));
      const deadline = Date.now() + 15000;
      while (!cancelled && loadingRef.current && Date.now() < deadline) {
        await new Promise((resolve) => window.setTimeout(resolve, 100));
      }
      if (cancelled) return;
      if (!store.markInitializing(localId)) return;
      try {
        await api.threads().item({ id: localId }).initialize();
      } catch {
        store.clearInitializing(localId);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    api,
    config.features.threads,
    config.ui_preset,
    store,
    threadsLoading,
    threadItem?.id,
    threadItem?.remoteId,
  ]);

  return null;
};
