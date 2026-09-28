"use client";

import { useEffect, useState } from "react";

import {
  DEFAULT_RUNTIME_CONFIG,
  fetchRuntimeConfig,
  resolveApiBase,
  type RuntimeConfig,
} from "@/lib/runtime-config";

/** Build-time connection default (split-port development). */
export const BUILD_TIME_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/assistant$/, "") ??
  "http://localhost:8010";

let cachedConfig: Promise<RuntimeConfig> | null = null;

function loadOnce(): Promise<RuntimeConfig> {
  cachedConfig ??= fetchRuntimeConfig();
  return cachedConfig;
}

export interface RuntimeConfigState {
  /** Manifest from the backend, or compiled defaults while loading. */
  config: RuntimeConfig;
  /** True once the backend manifest (or its fallback) has resolved. */
  loaded: boolean;
  /** Effective API base: runtime manifest wins, then build-time value. */
  apiBase: string;
}

/**
 * Load the runtime manifest once per page and derive the effective API
 * base. Before load, components behave exactly as with the build-time
 * constant; after load, deployment values apply without a rebuild.
 */
export function useRuntimeConfig(): RuntimeConfigState {
  const [config, setConfig] = useState<RuntimeConfig>(DEFAULT_RUNTIME_CONFIG);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    void loadOnce().then((next) => {
      if (!live) return;
      setConfig(next);
      setLoaded(true);
    });
    return () => {
      live = false;
    };
  }, []);

  return {
    config,
    loaded,
    apiBase: resolveApiBase(
      loaded ? config : null,
      BUILD_TIME_API_BASE,
      BUILD_TIME_API_BASE,
    ),
  };
}
