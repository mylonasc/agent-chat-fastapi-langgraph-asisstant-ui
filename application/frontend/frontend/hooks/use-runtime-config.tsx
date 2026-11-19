"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  DEFAULT_RUNTIME_CONFIG,
  fetchRuntimeConfig,
  resolveApiBase,
  type RuntimeConfig,
} from "@/lib/runtime-config";

/** Build-time connection default (split-port development). */
export const BUILD_TIME_API_BASE =
  (process.env.NEXT_PUBLIC_API_BASE === ""
    ? process.env.NEXT_PUBLIC_UI_BASE_PATH || ""
    : process.env.NEXT_PUBLIC_API_BASE) ??
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/assistant$/, "") ??
  "http://localhost:8010";

// Packaged builds fetch config from their public UI prefix. Split-port dev
// and Compose builds fetch it from the configured backend so the same bundle
// can select the minimal/full preset at runtime.
const BUILD_TIME_CONFIG_BASE =
  process.env.NEXT_PUBLIC_API_BASE === "" ||
  (process.env.NEXT_PUBLIC_API_BASE === undefined &&
    process.env.NEXT_PUBLIC_API_URL === undefined)
    ? process.env.NEXT_PUBLIC_UI_BASE_PATH || ""
    : (process.env.NEXT_PUBLIC_API_BASE ??
      process.env.NEXT_PUBLIC_API_URL?.replace(/\/assistant$/, "") ??
      "");

let cachedConfig: Promise<RuntimeConfig> | null = null;

function loadOnce(): Promise<RuntimeConfig> {
  cachedConfig ??= fetchRuntimeConfig({
    configBase: BUILD_TIME_CONFIG_BASE,
  });
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
function useRuntimeConfigState(): RuntimeConfigState {
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

const RuntimeConfigContext = createContext<RuntimeConfigState | null>(null);

/** Load deployment configuration once and share one snapshot with the app. */
export function RuntimeConfigProvider({ children }: { children: ReactNode }) {
  const value = useRuntimeConfigState();
  return (
    <RuntimeConfigContext.Provider value={value}>
      {children}
    </RuntimeConfigContext.Provider>
  );
}

export function useRuntimeConfig(): RuntimeConfigState {
  const value = useContext(RuntimeConfigContext);
  if (!value) {
    throw new Error(
      "useRuntimeConfig must be used within RuntimeConfigProvider",
    );
  }
  return value;
}
