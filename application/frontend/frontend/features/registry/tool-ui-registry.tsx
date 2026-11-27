"use client";

import {
  WebRAGStatusToolUI,
  WebRAGToolUI,
  WebSearchToolUI,
} from "@/features/rag/tool-ui";
import { GraphToolUI } from "@/features/graph/tool-ui";
import { isMinimalPreset, isWebRagEnabled } from "@/lib/capabilities";

import type { ToolUiRegistration } from "./types";

/**
 * Tool renderers keyed by the backend tool name they own.
 *
 * Adding a tool UI means appending one entry here; the host mounts only
 * entries whose capability gate passes, so a deployment that does not serve
 * Web RAG never registers its tool renderers (and never polls its status).
 */
export const TOOL_UI_REGISTRY: readonly ToolUiRegistration[] = [
  {
    id: "web-search",
    toolNames: ["web_search"],
    isEnabled: (config) =>
      isWebRagEnabled(config) ||
      Boolean(config.tooling?.tool_names.includes("web_search")),
    Component: WebSearchToolUI,
  },
  {
    id: "web-rag",
    toolNames: ["web_rag"],
    isEnabled: isWebRagEnabled,
    Component: WebRAGToolUI,
  },
  {
    id: "web-rag-status",
    toolNames: ["web_rag_status"],
    isEnabled: isWebRagEnabled,
    Component: WebRAGStatusToolUI,
  },
  {
    id: "render-graph",
    toolNames: ["render_graph"],
    isEnabled: (config) =>
      isMinimalPreset(config) ||
      Boolean(config.tooling?.tool_names.includes("render_graph")),
    Component: GraphToolUI,
  },
];
