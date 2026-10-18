"use client";

import { standardCatalog, useDataBinding } from "@a2ui-sdk/react/0.9";
import { ForceGraph } from "@/components/tools/GraphToolUI";

type PlainNode = { id: string; label?: string };
type PlainEdge = { source: string; target: string; label?: string };

// Custom catalog extension. Props resolve through useDataBinding, so the
// agent may send literals or {path} bindings into the surface data model;
// resolveValue passes non-path values through untouched.
function NetworkGraphComponent(props: {
  surfaceId: string;
  componentId: string;
  nodes?: unknown;
  edges?: unknown;
  directed?: unknown;
}) {
  const rawNodes = useDataBinding<unknown>(
    props.surfaceId,
    props.nodes as { path: string },
    [],
  );
  const rawEdges = useDataBinding<unknown>(
    props.surfaceId,
    props.edges as { path: string },
    [],
  );
  const rawDirected = useDataBinding<unknown>(
    props.surfaceId,
    props.directed as { path: string },
    false,
  );
  const nodes = (Array.isArray(rawNodes) ? rawNodes : []) as PlainNode[];
  const edges = (Array.isArray(rawEdges) ? rawEdges : []) as PlainEdge[];
  const cleanNodes = nodes
    .filter((n) => n && typeof n.id === "string")
    .map((n) => ({ id: n.id, label: n.label ?? n.id, weight: 50 }));
  const cleanEdges = edges
    .filter((e) => e && typeof e.source === "string" && typeof e.target === "string")
    .map((e) => ({ source: e.source, target: e.target, weight: 50 }));
  return (
    <ForceGraph
      data={{ directed: rawDirected === true, nodes: cleanNodes, edges: cleanEdges }}
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
