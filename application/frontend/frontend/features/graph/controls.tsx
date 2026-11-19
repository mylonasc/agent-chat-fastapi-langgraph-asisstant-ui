"use client";

import type { Dispatch, SetStateAction } from "react";

import type { GraphControlsState } from "./types";

export function GraphControls({
  directed,
  value,
  onChange,
}: {
  directed: boolean;
  value: GraphControlsState;
  onChange: Dispatch<SetStateAction<GraphControlsState>>;
}) {
  const range = (
    key: "charge" | "linkDistance" | "nodeScale" | "edgeScale",
    label: string,
    min: number,
    max: number,
    step: number,
  ) => (
    <label className="flex items-center gap-2">
      <span className="opacity-70">{label}</span>
      <input
        aria-label={label}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value[key]}
        onChange={(event) =>
          onChange((current) => ({
            ...current,
            [key]: Number(event.target.value),
          }))
        }
      />
      <span className="tabular-nums opacity-70">
        {key.endsWith("Scale") ? value[key].toFixed(1) : value[key]}
      </span>
    </label>
  );

  return (
    <div className="mb-3 grid gap-3 rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-4">
        {range("charge", "Charge", -900, -20, 10)}
        {range("linkDistance", "Link distance", 20, 220, 5)}
      </div>
      <div className="flex flex-wrap items-center gap-4">
        {range("nodeScale", "Node scale", 0.5, 2, 0.1)}
        {range("edgeScale", "Edge scale", 0.5, 2, 0.1)}
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={value.showLabels}
            onChange={(event) =>
              onChange((current) => ({
                ...current,
                showLabels: event.target.checked,
              }))
            }
          />
          <span className="opacity-70">Show labels</span>
        </label>
        <div className="ml-auto opacity-70">
          Mode: {directed ? "directed" : "undirected"}
        </div>
      </div>
    </div>
  );
}
