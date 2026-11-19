"use client";

import type { ReactNode } from "react";

import { ThreadSyncProvider } from "@/features/thread/thread-sync-store";
import { ApiClientProvider } from "@/hooks/use-api-client";
import { RuntimeConfigProvider } from "@/hooks/use-runtime-config";

/** Application-wide deployment configuration, identity, and API services. */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <RuntimeConfigProvider>
      <ApiClientProvider>
        <ThreadSyncProvider>{children}</ThreadSyncProvider>
      </ApiClientProvider>
    </RuntimeConfigProvider>
  );
}
