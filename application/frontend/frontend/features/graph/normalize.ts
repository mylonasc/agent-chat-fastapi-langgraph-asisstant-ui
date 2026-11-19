import type { GraphData, GraphEdge, GraphNode } from "./types";

type JsonObject = Record<string, unknown>;

function object(value: unknown): JsonObject | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : null;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function optionalWeight(value: unknown): number | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  const number = Number(value);
  return Number.isFinite(number)
    ? Math.max(0, Math.min(100, number))
    : undefined;
}

function node(value: unknown): GraphNode | null {
  const item = object(value);
  if (!item) return null;
  const id = optionalString(item.id);
  if (!id) return null;
  return {
    id,
    label: optionalString(item.label),
    weight: optionalWeight(item.weight),
  };
}

function edge(value: unknown, nodeIds: ReadonlySet<string>): GraphEdge | null {
  const item = object(value);
  if (!item) return null;
  const source = optionalString(item.source);
  const target = optionalString(item.target);
  if (!source || !target || !nodeIds.has(source) || !nodeIds.has(target))
    return null;
  return {
    source,
    target,
    label: optionalString(item.label),
    weight: optionalWeight(item.weight),
  };
}

/** Parse and validate untrusted graph tool output without leaking casts to UI. */
export function normalizeGraphResult(value: unknown): GraphData | null {
  let candidate = value;
  if (typeof candidate === "string") {
    try {
      candidate = JSON.parse(candidate);
    } catch {
      return null;
    }
  }
  const data = object(candidate);
  if (!data || !Array.isArray(data.nodes) || !Array.isArray(data.edges))
    return null;
  const nodes = data.nodes
    .map(node)
    .filter((item): item is GraphNode => item !== null);
  if (nodes.length === 0) return null;
  const nodeIds = new Set(nodes.map((item) => item.id));
  const edges = data.edges
    .map((item) => edge(item, nodeIds))
    .filter((item): item is GraphEdge => item !== null);
  return { directed: data.directed === true, nodes, edges };
}

/** React useId contains ':'; escape it into a fragment-safe SVG id. */
export function graphMarkerId(reactId: string): string {
  return `graph-arrow-${reactId.replace(/[^A-Za-z0-9_-]/g, "")}`;
}
