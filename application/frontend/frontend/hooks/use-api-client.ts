"use client";

import { useMemo } from "react";

import { ApiClient } from "@/lib/api-client";
import { useClientIdentity } from "@/lib/identity";
import { useRuntimeConfig } from "@/hooks/use-runtime-config";

/** Runtime-configured API client and the only identity source for UI calls. */
export function useApiClient() {
  const runtime = useRuntimeConfig();
  const identity = useClientIdentity(runtime.config.identity_mode);
  const client = useMemo(
    () => new ApiClient(runtime.apiBase, identity),
    [runtime.apiBase, identity],
  );
  return { ...runtime, identity, client };
}
