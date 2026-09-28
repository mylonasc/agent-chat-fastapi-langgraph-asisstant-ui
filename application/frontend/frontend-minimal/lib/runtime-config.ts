/**
 * Runtime UI configuration consumer (PUIR-08).
 *
 * One static build adapts at load time: the UI fetches `GET /api/config`
 * (same origin) and falls back to compiled defaults when the endpoint is
 * unavailable or malformed, so it always reaches a visible recoverable
 * state. This mirrors `agent_chat_minimal.runtime_config` schema v1.
 * Component wiring (preset switching, feature gating) is PUIR-09/PUIR-13.
 */

export const RUNTIME_CONFIG_VERSION = 1;

export type UiPreset = "minimal" | "full";
export type IdentityMode = "anonymous" | "delegated";

export interface ToolCapability {
  enabled: boolean;
  status_path: string | null;
}

export interface RuntimeConfig {
  version: number;
  api_base: string;
  ui_preset: UiPreset;
  identity_mode: IdentityMode;
  features: {
    agents: boolean;
    assistant: boolean;
    threads: boolean;
    transcripts: boolean;
  };
  tools: {
    web_rag: ToolCapability;
    admin: ToolCapability;
    sharing: ToolCapability;
    attachments: ToolCapability;
  };
}

export const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = {
  version: RUNTIME_CONFIG_VERSION,
  api_base: "",
  ui_preset: "minimal",
  identity_mode: "anonymous",
  features: { agents: true, assistant: true, threads: true, transcripts: true },
  tools: {
    web_rag: { enabled: false, status_path: "/tools/web_rag/status" },
    admin: { enabled: false, status_path: null },
    sharing: { enabled: false, status_path: null },
    attachments: { enabled: false, status_path: null },
  },
};

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function asBool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asString(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

/** Parse untrusted config data with backward-compatible defaults. */
export function parseRuntimeConfig(payload: unknown): RuntimeConfig {
  const data = asRecord(payload);
  const version =
    typeof data.version === "number" && data.version >= 1
      ? data.version
      : RUNTIME_CONFIG_VERSION;

  const rawFeatures = asRecord(data.features);
  const defaultFeatures = DEFAULT_RUNTIME_CONFIG.features;
  const features: RuntimeConfig["features"] = {
    agents: asBool(rawFeatures.agents, defaultFeatures.agents),
    assistant: asBool(rawFeatures.assistant, defaultFeatures.assistant),
    threads: asBool(rawFeatures.threads, defaultFeatures.threads),
    transcripts: asBool(rawFeatures.transcripts, defaultFeatures.transcripts),
  };

  const rawTools = asRecord(data.tools);
  const tool = (name: keyof RuntimeConfig["tools"]): ToolCapability => {
    const info = asRecord(rawTools[name]);
    const fallback = DEFAULT_RUNTIME_CONFIG.tools[name];
    const statusPath = asString(info.status_path, fallback.status_path ?? "");
    return {
      enabled: asBool(info.enabled, fallback.enabled),
      status_path: statusPath === "" ? null : statusPath,
    };
  };

  const uiPreset = asString(data.ui_preset, "minimal");
  const identityMode = asString(data.identity_mode, "anonymous");

  return {
    version,
    api_base: asString(data.api_base, ""),
    ui_preset: uiPreset === "full" ? "full" : "minimal",
    identity_mode: identityMode === "delegated" ? "delegated" : "anonymous",
    features,
    tools: {
      web_rag: tool("web_rag"),
      admin: tool("admin"),
      sharing: tool("sharing"),
      attachments: tool("attachments"),
    },
  };
}

export interface FetchRuntimeConfigOptions {
  /** Override the same-origin default (split-port development). */
  configBase?: string;
  /** Abort/timeout signal passthrough. */
  signal?: AbortSignal;
}

/**
 * Load the runtime config, degrading to compiled defaults when the
 * endpoint is missing, unreachable, or malformed.
 */
export async function fetchRuntimeConfig(
  options: FetchRuntimeConfigOptions = {},
): Promise<RuntimeConfig> {
  const base = options.configBase ?? "";
  try {
    const res = await fetch(`${base}/api/config`, {
      cache: "no-store",
      signal: options.signal,
    });
    if (!res.ok) return { ...DEFAULT_RUNTIME_CONFIG };
    return parseRuntimeConfig(await res.json());
  } catch {
    return { ...DEFAULT_RUNTIME_CONFIG };
  }
}

/**
 * Resolve the API base for backend calls. Runtime config wins (it is the
 * deployment contract); the build-time value covers split-port development
 * before the config loads; localhost is the last resort.
 */
export function resolveApiBase(
  config: RuntimeConfig | null,
  buildTimeFallback: string | undefined,
  localhostDefault: string,
): string {
  if (config?.api_base) return config.api_base;
  if (buildTimeFallback) return buildTimeFallback;
  return localhostDefault;
}
