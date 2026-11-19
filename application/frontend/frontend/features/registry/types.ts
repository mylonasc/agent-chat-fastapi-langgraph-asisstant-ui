import type { ComponentType } from "react";

import type { RuntimeConfig } from "@/lib/runtime-config";

/** A capability decision made against one deployment manifest. */
export type CapabilityGate = (config: RuntimeConfig) => boolean;

/**
 * A tool renderer contribution.
 *
 * Tool UIs register themselves with the assistant runtime by mounting; a
 * registry entry is all that is needed to add one. Entries declare the tool
 * names they own purely for discoverability and tests.
 */
export interface ToolUiRegistration {
  id: string;
  toolNames: readonly string[];
  isEnabled: CapabilityGate;
  Component: ComponentType;
}

/** A panel rendered inside the transcript, such as live indexing progress. */
export interface StatusPanelRegistration {
  id: string;
  isEnabled: CapabilityGate;
  Component: ComponentType;
}

/**
 * A navigation/action contribution.
 *
 * Every entry must have an implemented route and API contract; actions
 * without a backend (sharing) stay out of the registry until one exists.
 */
export interface HeaderActionRegistration {
  id: string;
  isEnabled: CapabilityGate;
  label: string;
  href: string;
}
