"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
  CheckCircle2Icon,
  Clock3Icon,
  Loader2Icon,
  SearchIcon,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";

type JsonObj = Record<string, unknown>;

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/assistant$/, "") ??
  "http://localhost:8010";

type SourceItem = {
  url: string;
  status: string;
  stage?: string;
  chunks?: number;
  documents?: number;
  parser?: string;
  error?: string | null;
};

function asObject(v: unknown): JsonObj {
  if (v && typeof v === "object") return v as JsonObj;
  if (typeof v === "string") {
    try {
      const parsed = JSON.parse(v);
      return parsed && typeof parsed === "object" ? (parsed as JsonObj) : {};
    } catch {
      return {};
    }
  }
  return {};
}

function toSources(raw: unknown): SourceItem[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((r) => asObject(r))
    .map((r) => ({
      url: String(r.url ?? ""),
      status: String(r.status ?? "queued"),
      stage: r.stage ? String(r.stage) : undefined,
      chunks: typeof r.chunks === "number" ? r.chunks : undefined,
      documents: typeof r.documents === "number" ? r.documents : undefined,
      parser: r.parser ? String(r.parser) : undefined,
      error: r.error ? String(r.error) : null,
    }))
    .filter((s) => s.url);
}

function badgeClass(status: string): string {
  const s = status.toLowerCase();
  if (s.includes("fail")) return "border-red-300 bg-red-50 text-red-700";
  if (s.includes("complete")) return "border-emerald-300 bg-emerald-50 text-emerald-700";
  if (s.includes("running") || s.includes("index") || s.includes("download")) {
    return "border-blue-300 bg-blue-50 text-blue-700";
  }
  return "border-amber-300 bg-amber-50 text-amber-700";
}

function StatusIcon({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s.includes("fail")) return <XCircleIcon className="size-4" />;
  if (s.includes("complete")) return <CheckCircle2Icon className="size-4" />;
  if (s.includes("running") || s.includes("index") || s.includes("download")) {
    return <Loader2Icon className="size-4 animate-spin" />;
  }
  return <Clock3Icon className="size-4" />;
}

function SourceIndexingPanel({
  toolName,
  args,
  statusType,
  result,
}: {
  toolName: string;
  args: JsonObj;
  statusType: string;
  result: JsonObj;
}) {
  const [panel, setPanel] = useState<"overview" | "sources" | "retrieval">("overview");
  const [expandedUrl, setExpandedUrl] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(statusType === "running");
  const [liveJobSources, setLiveJobSources] = useState<SourceItem[]>([]);
  const [remoteIndexStats, setRemoteIndexStats] = useState<{ sourceCount?: number; docCount?: number }>({});
  const [liveJobProgress, setLiveJobProgress] = useState<{
    status?: string;
    completedUrls?: number;
    failedUrls?: number;
    totalUrls?: number;
  }>({});

  const indexing = asObject(result.indexing);
  const rag = asObject(result.rag);
  const ragIndexing = asObject(rag.indexing);
  const jobs = Array.isArray(result.jobs) ? (result.jobs as JsonObj[]) : [];
  const activeJob =
    jobs.find((j) => {
      const s = String(asObject(j).status ?? "").toLowerCase();
      return s === "queued" || s === "running";
    }) ?? (jobs.length ? jobs[0] : undefined);
  const topJob = activeJob ? asObject(activeJob) : {};
  const effectiveIndexing =
    Object.keys(indexing).length
      ? indexing
      : Object.keys(ragIndexing).length
        ? ragIndexing
        : topJob;

  const indexerTool = String(effectiveIndexing.indexer_tool ?? "web_rag");
  const statusFromCall = String(
    effectiveIndexing.status ?? (statusType === "running" ? "running" : "completed")
  );
  const jobId = String(effectiveIndexing.job_id ?? "");
  const total = Number(
    effectiveIndexing.total_urls ??
      effectiveIndexing.queued_urls ??
      effectiveIndexing.total ??
      0
  );
  const completed = Number(effectiveIndexing.completed_urls ?? effectiveIndexing.completed ?? 0);
  const failed = Number(effectiveIndexing.failed_urls ?? effectiveIndexing.failed ?? 0);
  const parser = asObject(effectiveIndexing.parser ?? result.parser);
  const parserName = String(parser.pdf_parser ?? "pypdf");
  const parserDevice = String(parser.docling_device ?? "cpu");
  const sources = toSources(effectiveIndexing.sources ?? effectiveIndexing.items);

  const chunks = Array.isArray(rag.chunks)
    ? (rag.chunks as string[])
    : Array.isArray(result.chunks)
      ? (result.chunks as string[])
      : [];
  const retrievalSources = Array.isArray(rag.sources)
    ? (rag.sources as string[])
    : Array.isArray(result.sources)
      ? (result.sources as string[])
      : [];
  const topDocuments = Array.isArray(result.documents)
    ? (result.documents as JsonObj[]).slice(0, 5)
    : Array.isArray(result.results)
      ? (result.results as JsonObj[])
          .slice(0, 5)
          .map((r) => ({
            title: r.title,
            snippet: r.snippet,
            url: r.link ?? r.url,
          }))
      : [];
  const searchResults = Array.isArray(result.results) ? (result.results as JsonObj[]) : [];
  const indexStatus = asObject(result.index_status ?? result.index);
  const indexedSourceCount =
    typeof indexStatus.source_count === "number" ? Number(indexStatus.source_count) : null;
  const indexedDocumentCount =
    typeof indexStatus.document_count === "number" ? Number(indexStatus.document_count) : null;

  const fromRetrievalSources = useMemo<SourceItem[]>(() => {
    const fromRetrieval = Array.from(
      new Set(retrievalSources.filter((u): u is string => typeof u === "string" && !!u))
    ).map((u) => ({
      url: u,
      status: "retrieved",
      stage: "retrieved",
      documents: undefined,
      chunks: undefined,
      parser: undefined,
      error: null,
    }));
    return fromRetrieval;
  }, [retrievalSources]);

  const fromSearchSources = useMemo<SourceItem[]>(() => {
    return Array.from(
      new Set(
        searchResults
          .map((r) => String(r.link ?? r.url ?? ""))
          .filter((u) => !!u)
      )
    ).map((u) => ({
      url: u,
      status: "discovered",
      stage: "search_result",
      documents: undefined,
      chunks: undefined,
      parser: undefined,
      error: null,
    }));
  }, [searchResults]);

  const status = String(liveJobProgress.status ?? statusFromCall);
  const effectiveCompleted = Number(liveJobProgress.completedUrls ?? completed);
  const effectiveFailed = Number(liveJobProgress.failedUrls ?? failed);
  const effectiveJobTotal = Number(liveJobProgress.totalUrls ?? total);

  const mergedSources = useMemo(() => {
    if (liveJobSources.length) return liveJobSources;
    if (sources.length) return sources;
    if (fromRetrievalSources.length) return fromRetrievalSources;
    if (fromSearchSources.length) return fromSearchSources;
    return [];
  }, [fromRetrievalSources, fromSearchSources, liveJobSources, sources]);

  const sourceOrigin = useMemo(() => {
    if (liveJobSources.length) return "job_poll";
    if (sources.length) return "indexing";
    if (fromRetrievalSources.length) return "retrieval";
    if (fromSearchSources.length) return "search";
    return "none";
  }, [fromRetrievalSources.length, fromSearchSources.length, liveJobSources.length, sources.length]);

  const userId = String(args.user_id ?? result.user_id ?? "default_user");

  const effectiveTotal =
    effectiveJobTotal || total || mergedSources.length || indexedSourceCount || 0;
  const progressPct =
    effectiveTotal > 0
      ? Math.max(0, Math.min(100, Math.round((effectiveCompleted / effectiveTotal) * 100)))
      : status.toLowerCase().includes("complete")
        ? 100
        : 0;

  useEffect(() => {
    if (status.toLowerCase().includes("running")) {
      setIsOpen(true);
      return;
    }
    setIsOpen(false);
  }, [status]);

  useEffect(() => {
    let cancelled = false;

    const pollForLiveJob =
      !!jobId ||
      status.toLowerCase().includes("running") ||
      status.toLowerCase().includes("queued") ||
      statusType === "running";

    const fetchStatusOnly =
      !sources.length &&
      !retrievalSources.length &&
      !searchResults.length;

    if (!pollForLiveJob && !fetchStatusOnly) {
      return;
    }

    const run = async () => {
      try {
        const statusRes = await fetch(
          `${API_BASE}/tools/web_rag/status?user_id=${encodeURIComponent(userId)}`,
          { cache: "no-store" }
        );

        if (!statusRes.ok || cancelled) return;

        const statusJson = await statusRes.json();
        if (cancelled) return;

        const st = asObject(statusJson?.index);
        setRemoteIndexStats({
          sourceCount:
            typeof st.source_count === "number" ? Number(st.source_count) : undefined,
          docCount:
            typeof st.document_count === "number" ? Number(st.document_count) : undefined,
        });

        const jobList = Array.isArray(statusJson?.jobs) ? (statusJson.jobs as JsonObj[]) : [];
        const selectedJob =
          jobList.find((j) => String(asObject(j).job_id ?? "") === jobId) ??
          jobList.find((j) => {
            const s = String(asObject(j).status ?? "").toLowerCase();
            return s === "queued" || s === "running";
          });

        if (selectedJob) {
          const selected = asObject(selectedJob);
          setLiveJobProgress({
            status: String(selected.status ?? ""),
            completedUrls:
              typeof selected.completed_urls === "number"
                ? Number(selected.completed_urls)
                : undefined,
            failedUrls:
              typeof selected.failed_urls === "number"
                ? Number(selected.failed_urls)
                : undefined,
            totalUrls:
              typeof selected.total_urls === "number"
                ? Number(selected.total_urls)
                : undefined,
          });
          setLiveJobSources(toSources(selected.items ?? selected.sources));
        } else {
          setLiveJobSources([]);
        }
      } catch {
        // best-effort UI enhancement only
      }
    };

    void run();
    const pollId = window.setInterval(run, 1200);
    return () => {
      cancelled = true;
      window.clearInterval(pollId);
    };
  }, [jobId, retrievalSources.length, searchResults.length, sources.length, status, statusType, userId]);

  const callDocumentCount = useMemo(() => {
    if (sources.length) {
      return sources.reduce((acc, s) => acc + (typeof s.documents === "number" ? s.documents : 0), 0);
    }
    if (topDocuments.length) return topDocuments.length;
    return undefined;
  }, [sources, topDocuments.length]);

  return (
    <div
      data-testid={`source-indexing-widget-${toolName}`}
      className="mb-4 overflow-hidden rounded-2xl border bg-background shadow-sm"
    >
      <button
        type="button"
        data-testid={`source-indexing-widget-toggle-${toolName}`}
        className="flex w-full items-center justify-between border-b px-4 py-3 text-left"
        onClick={() => setIsOpen((v) => !v)}
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <StatusIcon status={status} />
          Source Indexing Widget
        </div>
        <div className="flex items-center gap-2">
          <div className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${badgeClass(status)}`}>
            {status}
          </div>
          <span className="text-xs text-muted-foreground">{isOpen ? "Collapse" : "Expand"}</span>
        </div>
      </button>

      {!isOpen ? null : (
        <>

      <div className="flex gap-2 border-b px-3 py-2">
        <Button variant={panel === "overview" ? "default" : "outline"} size="sm" onClick={() => setPanel("overview")}>
          Overview
        </Button>
        <Button variant={panel === "sources" ? "default" : "outline"} size="sm" onClick={() => setPanel("sources")}>
          Sources ({mergedSources.length})
        </Button>
        <Button variant={panel === "retrieval" ? "default" : "outline"} size="sm" onClick={() => setPanel("retrieval")}>
          Retrieval
        </Button>
      </div>

      {panel === "overview" && (
        <div className="grid gap-3 p-3 md:grid-cols-3">
          <div className="rounded-xl border bg-muted/30 p-3">
            <div className="mb-1 text-[11px] uppercase text-muted-foreground">Indexer Tool</div>
            <div className="flex items-center gap-2 text-sm font-medium">
              <WrenchIcon className="size-4" />
              {indexerTool}
            </div>
            {!!jobId && <div className="mt-1 break-all text-[11px] text-muted-foreground">job: {jobId}</div>}
            <div className="mt-1 text-[11px] text-muted-foreground">tool call: {toolName}</div>
          </div>

          <div className="rounded-xl border bg-muted/30 p-3">
            <div className="mb-1 text-[11px] uppercase text-muted-foreground">Progress</div>
            <div className="mb-2 text-sm font-medium">
              {effectiveTotal > 0
                ? `${effectiveCompleted}/${effectiveTotal} complete${effectiveFailed ? `, ${effectiveFailed} failed` : ""}`
                : "No active indexing in this call"}
            </div>
            <div className="h-2 w-full overflow-hidden rounded bg-muted">
              <div className="h-full rounded bg-primary" style={{ width: `${progressPct}%` }} />
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">{progressPct}%</div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              indexed docs: {indexedDocumentCount ?? remoteIndexStats.docCount ?? callDocumentCount ?? "n/a"} | indexed sources: {indexedSourceCount ?? remoteIndexStats.sourceCount ?? "n/a"}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              source list origin: {sourceOrigin}
            </div>
          </div>

          <div className="rounded-xl border bg-muted/30 p-3">
            <div className="mb-1 text-[11px] uppercase text-muted-foreground">Parser</div>
            <div className="text-sm font-medium">{parserName}</div>
            <div className="text-[11px] text-muted-foreground">device: {parserDevice}</div>
          </div>

          <div className="rounded-xl border bg-muted/30 p-3 md:col-span-3">
            <div className="mb-1 text-[11px] uppercase text-muted-foreground">Requested Tool Args</div>
            <div className="max-h-24 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">
              {JSON.stringify(args, null, 2)}
            </div>
          </div>
        </div>
      )}

      {panel === "sources" && (
        <div className="space-y-2 p-3">
          {!mergedSources.length && <div className="text-xs text-muted-foreground">No source entries available for this call.</div>}
          {mergedSources.map((src) => {
            const isOpen = expandedUrl === src.url;
            return (
              <div key={src.url} className="rounded-xl border">
                <button
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-left"
                  onClick={() => setExpandedUrl(isOpen ? null : src.url)}
                >
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium">{src.url}</div>
                    <div className="text-[11px] text-muted-foreground">stage: {src.stage ?? src.status}</div>
                  </div>
                  <span className={`rounded-full border px-2 py-0.5 text-[11px] ${badgeClass(src.status)}`}>
                    {src.status}
                  </span>
                </button>
                {isOpen && (
                  <div className="border-t bg-muted/20 px-3 py-2 text-xs">
                    <div>documents: {src.documents ?? 0}</div>
                    <div>chunks: {src.chunks ?? 0}</div>
                    <div>parser: {src.parser ?? parserName}</div>
                    {!!src.error && <div className="mt-1 text-red-700">error: {src.error}</div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {panel === "retrieval" && (
        <div className="grid gap-3 p-3 md:grid-cols-2">
          <div className="rounded-xl border bg-muted/20 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
              <SearchIcon className="size-3.5" />
              Top Documents
            </div>
            {!topDocuments.length && (
              <div className="text-xs text-muted-foreground">No document cards returned by this tool call.</div>
            )}
            {topDocuments.map((d, i) => (
              <div key={`${i}-${String(d.url ?? "")}`} className="mb-2 rounded border bg-background p-2 last:mb-0">
                <div className="line-clamp-1 text-xs font-medium">{String(d.title ?? "untitled")}</div>
                <div className="line-clamp-2 text-[11px] text-muted-foreground">{String(d.snippet ?? "")}</div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border bg-muted/20 p-3">
            <div className="mb-2 text-xs font-semibold uppercase text-muted-foreground">RAG Chunks</div>
            {!chunks.length && (
              <div className="text-xs text-muted-foreground">No chunks returned in this call (enable as_rag_chunks).</div>
            )}
            {chunks.slice(0, 3).map((c, i) => (
              <div key={`${i}-${c.slice(0, 24)}`} className="mb-2 rounded border bg-background p-2 text-xs last:mb-0">
                <div className="line-clamp-3">{c}</div>
                {retrievalSources[i] && (
                  <div className="mt-1 line-clamp-1 text-[11px] text-muted-foreground">source: {retrievalSources[i]}</div>
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

export const WebSearchToolUI = makeAssistantToolUI<JsonObj, JsonObj>({
  toolName: "web_search",
  render: ({ args, result, status, toolName }) => {
    if (!result && status.type === "running") {
      return (
        <div className="mb-3 rounded-xl border px-3 py-2 text-xs text-muted-foreground">
          <Loader2Icon className="mr-2 inline size-3.5 animate-spin" />
          web_search is running...
        </div>
      );
    }
    return <SourceIndexingPanel toolName={toolName} args={args as JsonObj} statusType={status.type} result={asObject(result)} />;
  },
});

export const WebRAGToolUI = makeAssistantToolUI<JsonObj, JsonObj>({
  toolName: "web_rag",
  render: ({ args, result, status, toolName }) => {
    if (!result && status.type === "running") {
      return (
        <div className="mb-3 rounded-xl border px-3 py-2 text-xs text-muted-foreground">
          <Loader2Icon className="mr-2 inline size-3.5 animate-spin" />
          web_rag is running...
        </div>
      );
    }
    return <SourceIndexingPanel toolName={toolName} args={args as JsonObj} statusType={status.type} result={asObject(result)} />;
  },
});

export const WebRAGStatusToolUI = makeAssistantToolUI<JsonObj, JsonObj>({
  toolName: "web_rag_status",
  render: ({ args, result, status, toolName }) => {
    if (!result && status.type === "running") {
      return (
        <div className="mb-3 rounded-xl border px-3 py-2 text-xs text-muted-foreground">
          <Loader2Icon className="mr-2 inline size-3.5 animate-spin" />
          web_rag_status is running...
        </div>
      );
    }
    return <SourceIndexingPanel toolName={toolName} args={args as JsonObj} statusType={status.type} result={asObject(result)} />;
  },
});
