/**
 * Capability gates derived from the deployment manifest.
 *
 * Components and registries use these predicates instead of reading flags
 * inline so a capability is enabled in exactly one place. A disabled
 * capability must both render no controls and issue no requests; the gates
 * are consumed by effects as well as JSX for that reason.
 */
import type { RuntimeConfig } from "@/lib/runtime-config";

export function isAssistantEnabled(config: RuntimeConfig): boolean {
  return config.features.assistant;
}

export function isAgentsEnabled(config: RuntimeConfig): boolean {
  return config.features.agents;
}

export function isThreadsEnabled(config: RuntimeConfig): boolean {
  return config.features.threads;
}

export function isTranscriptsEnabled(config: RuntimeConfig): boolean {
  return config.features.transcripts;
}

export function isWebRagEnabled(config: RuntimeConfig): boolean {
  return config.tools.web_rag.enabled;
}

export function isAdminEnabled(config: RuntimeConfig): boolean {
  return config.tools.admin.enabled;
}

export function isAttachmentsEnabled(config: RuntimeConfig): boolean {
  return config.tools.attachments.enabled;
}

/** The stripped-down single-thread preset that ships demo tool UIs. */
export function isMinimalPreset(config: RuntimeConfig): boolean {
  return config.ui_preset === "minimal";
}

/** The thread-list, sidebar, and multi-thread preset. */
export function isFullPreset(config: RuntimeConfig): boolean {
  return config.ui_preset === "full";
}
