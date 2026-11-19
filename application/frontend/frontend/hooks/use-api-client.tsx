"use client";

import { createContext, type ReactNode, useContext, useMemo } from "react";

import { ApiClient } from "@/lib/api-client";
import { useClientIdentity } from "@/lib/identity";
import { useRuntimeConfig } from "@/hooks/use-runtime-config";

function useApiClientState() {
  const runtime = useRuntimeConfig();
  const identity = useClientIdentity(runtime.config.identity_mode);
  const client = useMemo(
    () => new ApiClient(runtime.apiBase, identity),
    [runtime.apiBase, identity],
  );
  return { ...runtime, identity, client };
}

export type ApiClientState = ReturnType<typeof useApiClientState>;

const ApiClientContext = createContext<ApiClientState | null>(null);

/** Resolve browser identity and construct one API client for the application. */
export function ApiClientProvider({ children }: { children: ReactNode }) {
  const value = useApiClientState();
  return (
    <ApiClientContext.Provider value={value}>
      {children}
    </ApiClientContext.Provider>
  );
}

/** Runtime-configured API client and the only identity source for UI calls. */
export function useApiClient(): ApiClientState {
  const value = useContext(ApiClientContext);
  if (!value) {
    throw new Error("useApiClient must be used within ApiClientProvider");
  }
  return value;
}
