"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";

import { ForceGraph } from "./force-graph";
import { normalizeGraphResult } from "./normalize";

type GraphToolArgs = Record<string, unknown>;

export const GraphToolUI = makeAssistantToolUI<GraphToolArgs, unknown>({
  toolName: "render_graph",
  render: ({ status, result }) => {
    if (status.type === "running") {
      return (
        <div className="w-full rounded-lg border p-4 text-sm opacity-70">
          Rendering graph…
        </div>
      );
    }
    if (status.type === "incomplete" && status.reason === "error") {
      return (
        <div className="w-full rounded-lg border p-4 text-red-600">
          Tool failed to produce a graph.
        </div>
      );
    }
    const graph = normalizeGraphResult(result);
    if (!graph) {
      return (
        <div className="w-full rounded-lg border p-4">
          <div className="text-sm font-medium">Graph output</div>
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-black/5 p-3 text-xs">
            {typeof result === "string"
              ? result
              : JSON.stringify(result, null, 2)}
          </pre>
          <div className="mt-2 text-sm text-red-600">Invalid graph output</div>
        </div>
      );
    }
    return (
      <div className="w-full rounded-lg border p-4">
        <div className="mb-3 text-sm font-medium">
          Graph ({graph.nodes.length} nodes, {graph.edges.length} edges)
        </div>
        <ForceGraph data={graph} />
      </div>
    );
  },
});
