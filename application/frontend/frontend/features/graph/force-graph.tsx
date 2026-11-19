"use client";

import * as d3 from "d3";
import { useEffect, useId, useRef, useState } from "react";

import { GraphControls } from "./controls";
import { graphMarkerId } from "./normalize";
import type { GraphControlsState, GraphData, GraphNode } from "./types";

interface SimulationNode extends GraphNode, d3.SimulationNodeDatum {
  weight: number;
}

interface SimulationLink extends d3.SimulationLinkDatum<SimulationNode> {
  source: string | SimulationNode;
  target: string | SimulationNode;
  label?: string;
  weight: number;
}

const DEFAULT_CONTROLS: GraphControlsState = {
  charge: -250,
  linkDistance: 80,
  showLabels: true,
  nodeScale: 1,
  edgeScale: 1,
};

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function weight(value: number | undefined): number {
  return Math.max(0, Math.min(100, value ?? 50));
}

function coordinate(
  endpoint: string | SimulationNode,
  axis: "x" | "y",
): number {
  return typeof endpoint === "string" ? 0 : (endpoint[axis] ?? 0);
}

export function ForceGraph({
  data,
  height = 420,
}: {
  data: GraphData;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const markerId = graphMarkerId(useId());
  const [width, setWidth] = useState(800);
  const [controls, setControls] = useState(DEFAULT_CONTROLS);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver((entries) => {
      const nextWidth = entries[0]?.contentRect.width;
      if (nextWidth && nextWidth > 0) setWidth(nextWidth);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const svgElement = svgRef.current;
    if (!svgElement) return;
    const svg = d3.select(svgElement);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);
    const group = svg.append("g");
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.25, 4])
        .on("zoom", (event) =>
          group.attr("transform", event.transform.toString()),
        ),
    );

    if (data.directed) {
      svg
        .append("defs")
        .append("marker")
        .attr("id", markerId)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 16)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", "currentColor")
        .attr("fill-opacity", 0.55);
    }

    const nodes: SimulationNode[] = data.nodes.map((node) => ({
      ...node,
      weight: weight(node.weight),
    }));
    const links: SimulationLink[] = data.edges.map((edge) => ({
      ...edge,
      weight: weight(edge.weight),
    }));
    const radius = (value: number) =>
      (6 + (22 - 6) * clamp01(value / 100)) * controls.nodeScale;
    const edgeWidth = (value: number) =>
      (1 + (7 - 1) * clamp01(value / 100)) * controls.edgeScale;
    const edgeOpacity = (value: number) =>
      0.15 + (0.75 - 0.15) * clamp01(value / 100);
    const simulation = d3
      .forceSimulation<SimulationNode>(nodes)
      .alpha(0.9)
      .alphaDecay(0.08)
      .force(
        "link",
        d3
          .forceLink<SimulationNode, SimulationLink>(links)
          .id((node) => node.id)
          .distance(controls.linkDistance),
      )
      .force(
        "charge",
        d3.forceManyBody<SimulationNode>().strength(controls.charge),
      )
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collide",
        d3.forceCollide<SimulationNode>((node) => radius(node.weight) + 4),
      );
    simulation.tick(30);

    const link = group
      .append("g")
      .selectAll<SVGLineElement, SimulationLink>("line")
      .data(links)
      .join("line")
      .attr("stroke", "currentColor")
      .attr("stroke-width", (item) => edgeWidth(item.weight))
      .attr("stroke-opacity", (item) => edgeOpacity(item.weight))
      .attr("marker-end", data.directed ? `url(#${markerId})` : null);
    const node = group
      .append("g")
      .selectAll<SVGCircleElement, SimulationNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (item) => radius(item.weight))
      .attr("fill", "currentColor")
      .attr("fill-opacity", 0.9)
      .call(
        d3
          .drag<SVGCircleElement, SimulationNode>()
          .on("start", (event, item) => {
            if (!event.active) simulation.alphaTarget(0.2).restart();
            item.fx = item.x;
            item.fy = item.y;
          })
          .on("drag", (event, item) => {
            item.fx = event.x;
            item.fy = event.y;
          })
          .on("end", (event, item) => {
            if (!event.active) simulation.alphaTarget(0);
            item.fx = null;
            item.fy = null;
          }),
      );
    const label = group
      .append("g")
      .style("display", controls.showLabels ? "block" : "none")
      .selectAll<SVGTextElement, SimulationNode>("text")
      .data(nodes)
      .join("text")
      .text((item) => item.label ?? item.id)
      .attr("font-size", 12)
      .attr("dx", (item) => radius(item.weight) + 6)
      .attr("dy", 4)
      .attr("fill", "currentColor")
      .attr("fill-opacity", 0.85);

    simulation.on("tick", () => {
      link
        .attr("x1", (item) => coordinate(item.source, "x"))
        .attr("y1", (item) => coordinate(item.source, "y"))
        .attr("x2", (item) => coordinate(item.target, "x"))
        .attr("y2", (item) => coordinate(item.target, "y"));
      node.attr("cx", (item) => item.x ?? 0).attr("cy", (item) => item.y ?? 0);
      label.attr("x", (item) => item.x ?? 0).attr("y", (item) => item.y ?? 0);
    });
    return () => {
      simulation.stop();
    };
  }, [controls, data, height, markerId, width]);

  return (
    <div ref={containerRef} className="w-full">
      <GraphControls
        directed={data.directed}
        value={controls}
        onChange={setControls}
      />
      <svg
        ref={svgRef}
        data-graph-marker-id={markerId}
        aria-label="Interactive force graph"
        className="h-[420px] w-full rounded-lg border"
      />
    </div>
  );
}
