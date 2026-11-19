"use client";

import { IndexingStatusPanel } from "@/features/rag/indexing-status-panel";
import { isWebRagEnabled } from "@/lib/capabilities";

import type { StatusPanelRegistration } from "./types";

/**
 * Panels rendered below the transcript.
 *
 * Each entry is responsible for its own rendering, but mounting is gated
 * here so a disabled capability performs no polling or background work.
 */
export const STATUS_PANEL_REGISTRY: readonly StatusPanelRegistration[] = [
  {
    id: "rag-indexing",
    isEnabled: isWebRagEnabled,
    Component: IndexingStatusPanel,
  },
];
