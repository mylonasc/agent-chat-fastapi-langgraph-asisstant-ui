"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { Loader2Icon } from "lucide-react";

import { SourceIndexingPanel } from "./source-indexing-panel";
import { asJsonObject, type JsonObject } from "./source-normalize";

function RunningTool({ name }: { name: string }) {
  return (
    <div className="mb-3 rounded-xl border px-3 py-2 text-xs text-muted-foreground">
      <Loader2Icon className="mr-2 inline size-3.5 animate-spin" />
      {name} is running...
    </div>
  );
}

function makeSourceTool(toolName: string) {
  return makeAssistantToolUI<JsonObject, unknown>({
    toolName,
    render: ({ args, result, status }) =>
      !result && status.type === "running" ? (
        <RunningTool name={toolName} />
      ) : (
        <SourceIndexingPanel
          toolName={toolName}
          args={asJsonObject(args)}
          statusType={status.type}
          result={result}
        />
      ),
  });
}

export const WebSearchToolUI = makeSourceTool("web_search");
export const WebRAGToolUI = makeSourceTool("web_rag");
export const WebRAGStatusToolUI = makeSourceTool("web_rag_status");
