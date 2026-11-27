"use client";

import {
  CheckCircle2Icon,
  Clock3Icon,
  Loader2Icon,
  SearchIcon,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import type { RagSourceItem } from "@/lib/api/types";

import {
  normalizeSourceIndexingResult,
  retrievalSourceItems,
  type JsonObject,
} from "./source-normalize";
import {
  hasActiveRagJobs,
  useRagStatusPolling,
} from "./use-rag-status-polling";

function badgeClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized.includes("fail"))
    return "border-red-300 bg-red-50 text-red-700";
  if (normalized.includes("complete")) {
    return "border-emerald-300 bg-emerald-50 text-emerald-700";
  }
  if (
    ["running", "index", "download"].some((part) => normalized.includes(part))
  ) {
    return "border-blue-300 bg-blue-50 text-blue-700";
  }
  return "border-amber-300 bg-amber-50 text-amber-700";
}

function StatusIcon({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  if (normalized.includes("fail")) return <XCircleIcon className="size-4" />;
  if (normalized.includes("complete"))
    return <CheckCircle2Icon className="size-4" />;
  if (
    ["running", "index", "download"].some((part) => normalized.includes(part))
  ) {
    return <Loader2Icon className="size-4 animate-spin" />;
  }
  return <Clock3Icon className="size-4" />;
}

export function SourceIndexingPanel({
  toolName,
  args,
  statusType,
  result,
}: {
  toolName: string;
  args: JsonObject;
  statusType: string;
  result: unknown;
}) {
  const model = useMemo(
    () => normalizeSourceIndexingResult(result, statusType),
    [result, statusType],
  );
  const [panel, setPanel] = useState<"overview" | "sources" | "retrieval">(
    "overview",
  );
  const [expandedUrl, setExpandedUrl] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(statusType === "running");
  const shouldPoll =
    Boolean(model.jobId) ||
    ["queued", "running"].includes(model.status.toLowerCase()) ||
    (!model.sources.length &&
      !model.retrievalSources.length &&
      !model.searchSources.length);
  const { data: liveStatus } = useRagStatusPolling({
    enabled: shouldPoll,
    continueWhile: (status) =>
      hasActiveRagJobs(status) &&
      (!model.jobId || status.jobs.some((job) => job.job_id === model.jobId)),
  });
  const liveJob =
    liveStatus?.jobs.find((job) => job.job_id === model.jobId) ??
    liveStatus?.jobs.find((job) =>
      ["queued", "running"].includes(job.status.toLowerCase()),
    );
  const retrievalSources = useMemo(
    () => retrievalSourceItems(model.retrievalSources),
    [model.retrievalSources],
  );
  const mergedSources: RagSourceItem[] = liveJob?.items.length
    ? liveJob.items
    : model.sources.length
      ? model.sources
      : retrievalSources.length
        ? retrievalSources
        : model.searchSources;
  const sourceOrigin = liveJob?.items.length
    ? "job_poll"
    : model.sources.length
      ? "indexing"
      : retrievalSources.length
        ? "retrieval"
        : model.searchSources.length
          ? "search"
          : "none";
  const status = liveJob?.status ?? model.status;
  const completed = liveJob?.completed_urls ?? model.completed;
  const failed = liveJob?.failed_urls ?? model.failed;
  const total =
    liveJob?.total_urls ||
    model.total ||
    mergedSources.length ||
    model.indexedSourceCount ||
    0;
  const progress =
    total > 0
      ? Math.max(0, Math.min(100, Math.round((completed / total) * 100)))
      : status.toLowerCase().includes("complete")
        ? 100
        : 0;
  const documentCount = model.sources.reduce(
    (sum, source) => sum + (source.documents ?? 0),
    0,
  );

  return (
    <div
      data-testid={`source-indexing-widget-${toolName}`}
      className="@container mb-4 overflow-hidden rounded-2xl border bg-background shadow-sm"
    >
      <button
        type="button"
        data-testid={`source-indexing-widget-toggle-${toolName}`}
        className="flex w-full flex-wrap items-center justify-between gap-2 border-b px-4 py-3 text-left"
        onClick={() => setIsOpen((open) => !open)}
      >
        <span className="flex items-center gap-2 text-sm font-semibold">
          <StatusIcon status={status} />
          Source Indexing Widget
        </span>
        <span className="flex items-center gap-2">
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${badgeClass(status)}`}
          >
            {status}
          </span>
          <span className="text-xs text-muted-foreground">
            {isOpen ? "Collapse" : "Expand"}
          </span>
        </span>
      </button>

      {isOpen && (
        <>
          <div className="flex flex-wrap gap-2 border-b px-3 py-2">
            {(["overview", "sources", "retrieval"] as const).map((name) => (
              <Button
                key={name}
                variant={panel === name ? "default" : "outline"}
                size="sm"
                onClick={() => setPanel(name)}
              >
                {name === "sources"
                  ? `Sources (${mergedSources.length})`
                  : `${name[0]!.toUpperCase()}${name.slice(1)}`}
              </Button>
            ))}
          </div>

          {panel === "overview" && (
            <div className="grid gap-3 p-3 @md:grid-cols-3">
              <div className="rounded-xl border bg-muted/30 p-3">
                <div className="mb-1 text-[11px] text-muted-foreground uppercase">
                  Indexer Tool
                </div>
                <div className="flex items-center gap-2 text-sm font-medium">
                  <WrenchIcon className="size-4" />
                  {model.indexerTool}
                </div>
                {model.jobId && (
                  <div className="mt-1 text-[11px] break-all text-muted-foreground">
                    job: {model.jobId}
                  </div>
                )}
                <div className="mt-1 text-[11px] text-muted-foreground">
                  tool call: {toolName}
                </div>
              </div>

              <div className="rounded-xl border bg-muted/30 p-3">
                <div className="mb-1 text-[11px] text-muted-foreground uppercase">
                  Progress
                </div>
                <div className="mb-2 text-sm font-medium">
                  {total > 0
                    ? `${completed}/${total} complete${failed ? `, ${failed} failed` : ""}`
                    : "No active indexing in this call"}
                </div>
                <div className="h-2 w-full overflow-hidden rounded bg-muted">
                  <div
                    className="h-full rounded bg-primary"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  {progress}%
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  indexed docs:{" "}
                  {(model.indexedDocumentCount ??
                    liveStatus?.index.document_count ??
                    documentCount) ||
                    "n/a"}{" "}
                  | indexed sources:{" "}
                  {model.indexedSourceCount ??
                    liveStatus?.index.source_count ??
                    "n/a"}
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  source list origin: {sourceOrigin}
                </div>
              </div>

              <div className="rounded-xl border bg-muted/30 p-3">
                <div className="mb-1 text-[11px] text-muted-foreground uppercase">
                  Parser
                </div>
                <div className="text-sm font-medium">{model.parserName}</div>
                <div className="text-[11px] text-muted-foreground">
                  device: {model.parserDevice}
                </div>
              </div>

              <div className="rounded-xl border bg-muted/30 p-3 @md:col-span-3">
                <div className="mb-1 text-[11px] text-muted-foreground uppercase">
                  Requested Tool Args
                </div>
                <pre className="max-h-24 overflow-auto text-xs whitespace-pre-wrap text-muted-foreground">
                  {JSON.stringify(args, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {panel === "sources" && (
            <div className="space-y-2 p-3">
              {!mergedSources.length && (
                <div className="text-xs text-muted-foreground">
                  No source entries available for this call.
                </div>
              )}
              {mergedSources.map((source) => {
                const expanded = expandedUrl === source.url;
                return (
                  <div key={source.url} className="rounded-xl border">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between px-3 py-2 text-left"
                      onClick={() =>
                        setExpandedUrl(expanded ? null : source.url)
                      }
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-medium">
                          {source.url}
                        </span>
                        <span className="text-[11px] text-muted-foreground">
                          stage: {source.stage ?? source.status}
                        </span>
                      </span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[11px] ${badgeClass(source.status)}`}
                      >
                        {source.status}
                      </span>
                    </button>
                    {expanded && (
                      <div className="border-t bg-muted/20 px-3 py-2 text-xs">
                        <div>documents: {source.documents ?? 0}</div>
                        <div>chunks: {source.chunks ?? 0}</div>
                        <div>parser: {source.parser ?? model.parserName}</div>
                        {source.error && (
                          <div className="mt-1 text-red-700">
                            error: {source.error}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {panel === "retrieval" && (
            <div className="grid gap-3 p-3 @md:grid-cols-2">
              <div className="rounded-xl border bg-muted/20 p-3">
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase">
                  <SearchIcon className="size-3.5" /> Top Documents
                </div>
                {!model.documents.length && (
                  <div className="text-xs text-muted-foreground">
                    No document cards returned by this tool call.
                  </div>
                )}
                {model.documents.map((document, index) => (
                  <div
                    key={`${index}-${document.url}`}
                    className="mb-2 rounded border bg-background p-2 last:mb-0"
                  >
                    <div className="line-clamp-1 text-xs font-medium">
                      {document.title}
                    </div>
                    <div className="line-clamp-2 text-[11px] text-muted-foreground">
                      {document.snippet}
                    </div>
                  </div>
                ))}
              </div>
              <div className="rounded-xl border bg-muted/20 p-3">
                <div className="mb-2 text-xs font-semibold text-muted-foreground uppercase">
                  RAG Chunks
                </div>
                {!model.chunks.length && (
                  <div className="text-xs text-muted-foreground">
                    No chunks returned in this call (enable as_rag_chunks).
                  </div>
                )}
                {model.chunks.slice(0, 3).map((chunk, index) => (
                  <div
                    key={`${index}-${chunk.slice(0, 24)}`}
                    className="mb-2 rounded border bg-background p-2 text-xs last:mb-0"
                  >
                    <div className="line-clamp-3">{chunk}</div>
                    {model.retrievalSources[index] && (
                      <div className="mt-1 line-clamp-1 text-[11px] text-muted-foreground">
                        source: {model.retrievalSources[index]}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
