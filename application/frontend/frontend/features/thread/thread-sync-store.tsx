"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

/**
 * Cross-remount bookkeeping for transcript sync and thread initialization.
 *
 * Both values used to live in module-level maps/sets, which made them global
 * mutable state shared by every runtime. A provider keeps the same
 * "survives a thread remount" lifetime while scoping the state to the mounted
 * application.
 */
export type ThreadSyncStore = {
  /** Payloads already written for a thread, keyed by message id. */
  getSyncedPayloads(threadKey: string): Map<string, string>;
  isInitializing(threadId: string): boolean;
  /** Returns false when the thread is already being initialized. */
  markInitializing(threadId: string): boolean;
  clearInitializing(threadId: string): void;
};

const ThreadSyncContext = createContext<ThreadSyncStore | null>(null);

export function ThreadSyncProvider({ children }: { children: ReactNode }) {
  const syncedPayloadsByThread = useRef(new Map<string, Map<string, string>>());
  const initializingThreadIds = useRef(new Set<string>());

  const getSyncedPayloads = useCallback((threadKey: string) => {
    const existing = syncedPayloadsByThread.current.get(threadKey);
    if (existing) return existing;
    const created = new Map<string, string>();
    syncedPayloadsByThread.current.set(threadKey, created);
    return created;
  }, []);

  const isInitializing = useCallback(
    (threadId: string) => initializingThreadIds.current.has(threadId),
    [],
  );

  const markInitializing = useCallback((threadId: string) => {
    if (initializingThreadIds.current.has(threadId)) return false;
    initializingThreadIds.current.add(threadId);
    return true;
  }, []);

  const clearInitializing = useCallback((threadId: string) => {
    initializingThreadIds.current.delete(threadId);
  }, []);

  const value = useMemo(
    () => ({
      getSyncedPayloads,
      isInitializing,
      markInitializing,
      clearInitializing,
    }),
    [clearInitializing, getSyncedPayloads, isInitializing, markInitializing],
  );

  return (
    <ThreadSyncContext.Provider value={value}>
      {children}
    </ThreadSyncContext.Provider>
  );
}

export function useThreadSyncStore(): ThreadSyncStore {
  const store = useContext(ThreadSyncContext);
  if (!store) {
    throw new Error(
      "useThreadSyncStore must be used within ThreadSyncProvider",
    );
  }
  return store;
}
