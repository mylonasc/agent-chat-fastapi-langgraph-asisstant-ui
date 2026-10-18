"use client";

import { standardCatalog } from "@a2ui-sdk/react/0.9";
import { ForceGraph } from "@/components/tools/GraphToolUI";

type PlainNode = { id: string; label?: string };
type PlainEdge = { source: string; target: string; label?: string };

// Custom catalog extension. Literal props only (no path bindings) so the
// component paints on first render without data-model resolution.
function NetworkGraphComponent(props: {
  surfaceId: string;
  componentId: string;
  nodes?: unknown;
  edges?: unknown;
  directed?: unknown;
}) {
  const nodes = (Array.isArray(props.nodes) ? props.nodes : []) as PlainNode[];
  const edges = (Array.isArray(props.edges) ? props.edges : []) as PlainEdge[];
  const cleanNodes = nodes
    .filter((n) => n && typeof n.id === "string")
    .map((n) => ({ id: n.id, label: n.label ?? n.id, weight: 50 }));
  const cleanEdges = edges
    .filter((e) => e && typeof e.source === "string" && typeof e.target === "string")
    .map((e) => ({ source: e.source, target: e.target, weight: 50 }));
  return (
    <ForceGraph
      data={{ directed: props.directed === true, nodes: cleanNodes, edges: cleanEdges }}
    />
  );
}

export const customCatalog = {
  ...standardCatalog,
  components: {
    ...standardCatalog.components,
    NetworkGraph: NetworkGraphComponent,
  },
};
