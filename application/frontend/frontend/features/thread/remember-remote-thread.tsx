"use client";

import { useAssistantApi, useAssistantState } from "@assistant-ui/react";
import { useEffect, useRef, type FC } from "react";

import { useApiClient } from "@/hooks/use-api-client";

const ACTIVE_THREAD_STORAGE_KEY = "agent-chat.active-thread.v1";

/** Restore the user's selected owned thread rather than a fresh local draft. */
export const RememberRemoteThread: FC = () => {
  const api = useAssistantApi();
  const { config } = useApiClient();
  const threadItem = useAssistantState((state) => state.threadListItem);
  // A transport-only runtime has no `threads` scope; the optional chain
  // keeps this hook safe when the thread-list capability is disabled.
  const isLoading = useAssistantState(
    (state) => state.threads?.isLoading ?? false,
  );
  const threadItems = useAssistantState(
    (state) => state.threads?.threadItems ?? [],
  );
  const restoredInitialThread = useRef(false);

  useEffect(() => {
    // Thread restoration is meaningless without a thread list.
    if (!config.features.threads) return;
    if (threadItem?.remoteId) {
      localStorage.setItem(ACTIVE_THREAD_STORAGE_KEY, threadItem.remoteId);
      return;
    }
    if (isLoading || restoredInitialThread.current) return;
    const saved = localStorage.getItem(ACTIVE_THREAD_STORAGE_KEY);
    if (!saved) {
      restoredInitialThread.current = true;
      return;
    }
    const match = threadItems.find((item) => item.remoteId === saved);
    if (!match) return;
    restoredInitialThread.current = true;
    if (match.status === "archived") {
      // Never resurrect an archived thread: switching to it would unarchive
      // it server-side and drag it back into the list. Forget the saved id
      // so the UI settles on a fresh thread instead.
      localStorage.removeItem(ACTIVE_THREAD_STORAGE_KEY);
      return;
    }
    api.threads().switchToThread(saved);
  }, [
    api,
    config.features.threads,
    isLoading,
    threadItems,
    threadItem?.remoteId,
  ]);

  return null;
};
