"use client";





"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import React, { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

type GraphNode = { id: string; label?: string; weight?: number };
type GraphEdge = { source: string; target: string; label?: string; weight?: number };
type GraphToolResult = { directed?: boolean; nodes: GraphNode[]; edges: GraphEdge[] };

type GraphToolArgs = {
  // whatever the model passes to the tool (optional)
  // e.g. query: string;
};


function clamp01(x: number) {
  return Math.max(0, Math.min(1, x));
}
function clamp100(x: any, fallback = 50) {
  const v = Number.isFinite(Number(x)) ? Number(x) : fallback;
  return Math.max(0, Math.min(100, v));
}
function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export function ForceGraph({
  data,
  height = 420,
}: {
  data: GraphToolResult;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [width, setWidth] = useState(800);

  // Advanced controls
  const [charge, setCharge] = useState(-250);
  const [linkDistance, setLinkDistance] = useState(80);
  const [showLabels, setShowLabels] = useState(true);
  const [nodeScale, setNodeScale] = useState(1); // multiplier
  const [edgeScale, setEdgeScale] = useState(1); // multiplier

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w && w > 0) setWidth(w);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const directed = !!data.directed;

    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    // Zoom/pan
    const g = svg.append("g");
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.25, 4])
        .on("zoom", (event) => g.attr("transform", event.transform.toString()))
    );

    // Arrowhead marker (only if directed)
    if (directed) {
      const defs = svg.append("defs");
      defs
        .append("marker")
        .attr("id", "arrow")
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 16) // pushes arrow away from node center; tuned later
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", "currentColor")
        .attr("fill-opacity", 0.55);
    }

    // Copy data so D3 can mutate safely
    const nodes = (data.nodes ?? []).map((n) => ({
      ...n,
      weight: clamp100(n.weight, 50),
    })) as Array<GraphNode & d3.SimulationNodeDatum>;

    const links = (data.edges ?? []).map((e) => ({
      ...e,
      weight: clamp100(e.weight, 50),
    })) as Array<
      { source: string; target: string; label?: string; weight: number } & d3.SimulationLinkDatum<
        GraphNode & d3.SimulationNodeDatum
      >
    >;

    // Weight mappings
    const nodeRadius = (w: number) => lerp(6, 22, clamp01(w / 100)) * nodeScale;
    const edgeWidth = (w: number) => lerp(1, 7, clamp01(w / 100)) * edgeScale;
    const edgeOpacity = (w: number) => lerp(0.15, 0.75, clamp01(w / 100));

    // Simulation (less jitter: gentler alpha decay + pre-ticks)
    const sim = d3
      .forceSimulation(nodes)
      .alpha(0.9)
      .alphaDecay(0.08)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d: any) => d.id)
          .distance(linkDistance)
      )
      .force("charge", d3.forceManyBody().strength(charge))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collide",
        d3.forceCollide((d: any) => nodeRadius(d.weight ?? 50) + 4)
      );

    // Pre-tick a bit so the first paint is already “settled”
    sim.tick(30);

    // Links
    const link = g
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "currentColor")
      .attr("stroke-width", (d: any) => edgeWidth(d.weight))
      .attr("stroke-opacity", (d: any) => edgeOpacity(d.weight))
      .attr("marker-end", directed ? "url(#arrow)" : null);

    // Nodes
    const node = g
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d: any) => nodeRadius(d.weight ?? 50))
      .attr("fill", "currentColor")
      .attr("fill-opacity", 0.9)
      .call(
        d3
          .drag<SVGCircleElement, any>()
          .on("start", (event, d) => {
            if (!event.active) sim.alphaTarget(0.2).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Labels
    const label = g
      .append("g")
      .style("display", showLabels ? "block" : "none")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text((d) => d.label ?? d.id)
      .attr("font-size", 12)
      .attr("dx", (d: any) => nodeRadius(d.weight ?? 50) + 6)
      .attr("dy", 4)
      .attr("fill", "currentColor")
      .attr("fill-opacity", 0.85);

    // Tick updates
    sim.on("tick", () => {
      // For directed graphs, shorten link so arrow doesn’t overlap node:
      link
        .attr("x1", (d: any) => (d.source as any).x)
        .attr("y1", (d: any) => (d.source as any).y)
        .attr("x2", (d: any) => (d.target as any).x)
        .attr("y2", (d: any) => (d.target as any).y);

      node.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y);

      label.attr("x", (d: any) => d.x).attr("y", (d: any) => d.y);
    });

    return () => sim.stop();
  }, [data, width, height, charge, linkDistance, showLabels, nodeScale, edgeScale]);

  return (
    <div ref={containerRef} className="w-full">
      <div className="mb-3 grid gap-3 rounded-lg border p-3 text-sm">
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2">
            <span className="opacity-70">Charge</span>
            <input
              type="range"
              min={-900}
              max={-20}
              step={10}
              value={charge}
              onChange={(e) => setCharge(Number(e.target.value))}
            />
            <span className="tabular-nums opacity-70">{charge}</span>
          </label>

          <label className="flex items-center gap-2">
            <span className="opacity-70">Link distance</span>
            <input
              type="range"
              min={20}
              max={220}
              step={5}
              value={linkDistance}
              onChange={(e) => setLinkDistance(Number(e.target.value))}
            />
            <span className="tabular-nums opacity-70">{linkDistance}</span>
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2">
            <span className="opacity-70">Node scale</span>
            <input
              type="range"
              min={0.5}
              max={2}
              step={0.1}
              value={nodeScale}
              onChange={(e) => setNodeScale(Number(e.target.value))}
            />
            <span className="tabular-nums opacity-70">{nodeScale.toFixed(1)}</span>
          </label>

          <label className="flex items-center gap-2">
            <span className="opacity-70">Edge scale</span>
            <input
              type="range"
              min={0.5}
              max={2}
              step={0.1}
              value={edgeScale}
              onChange={(e) => setEdgeScale(Number(e.target.value))}
            />
            <span className="tabular-nums opacity-70">{edgeScale.toFixed(1)}</span>
          </label>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
            />
            <span className="opacity-70">Show labels</span>
          </label>

          <div className="ml-auto opacity-70">
            Mode: {data.directed ? "directed" : "undirected"}
          </div>
        </div>
      </div>

      <svg ref={svgRef} className="h-[420px] w-full rounded-lg border" />
    </div>
  );
}


// ----- Tool UI registration -----
// UI-only: you’re not defining execute() here, just rendering tool calls/results.
export const GraphToolUI = makeAssistantToolUI<GraphToolArgs, unknown>({
  toolName: "render_graph", // MUST match backend tool name
  render: ({ status, result }) => {
    if (status.type === "running") {
      return (
        <div className="w-full rounded-lg border p-4">
          <div className="text-sm opacity-70">Rendering graph…</div>
        </div>
      );
    }

    // result might already be an object depending on your runtime; handle both.
    let parsed: GraphToolResult | null = null;
    let error: string | null = null;

    try {
      if (typeof result === "string") parsed = JSON.parse(result);
      else parsed = result as GraphToolResult;
    } catch (e: any) {
      error = e?.message ?? "Failed to parse graph JSON";
    }

    if (status.type === "incomplete" && status.reason === "error") {
      return (
        <div className="w-full rounded-lg border p-4 text-red-600">
          Tool failed to produce a graph.
        </div>
      );
    }

    if (error || !parsed?.nodes || !parsed?.edges) {
      return (
        <div className="w-full rounded-lg border p-4">
          <div className="text-sm font-medium">Graph output</div>
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-black/5 p-3 text-xs">
            {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
          </pre>
          {error && <div className="mt-2 text-sm text-red-600">{error}</div>}
        </div>
      );
    }

    return (
      <div className="w-full rounded-lg border p-4">
        <div className="mb-3 text-sm font-medium">
          Graph ({parsed.nodes.length} nodes, {parsed.edges.length} edges)
        </div>
        <ForceGraph data={parsed} />
      </div>
    );
  },
});
