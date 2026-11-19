import { normalizeRagSourceItem } from "@/lib/api/normalize";
import type { RagSourceItem } from "@/lib/api/types";

export type JsonObject = Record<string, unknown>;

export interface SourceDocument {
  title: string;
  snippet: string;
  url: string;
}

export interface SourceIndexingViewModel {
  indexerTool: string;
  status: string;
  jobId: string;
  total: number;
  completed: number;
  failed: number;
  parserName: string;
  parserDevice: string;
  sources: RagSourceItem[];
  retrievalSources: string[];
  searchSources: RagSourceItem[];
  chunks: string[];
  documents: SourceDocument[];
  indexedSourceCount: number | null;
  indexedDocumentCount: number | null;
}

export function asJsonObject(value: unknown): JsonObject {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as JsonObject;
  }
  if (typeof value !== "string") return {};
  try {
    return asJsonObject(JSON.parse(value));
  } catch {
    return {};
  }
}

function finiteNumber(value: unknown): number {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : 0;
}

function strings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is string => typeof item === "string" && item.length > 0,
  );
}

function objects(value: unknown): JsonObject[] {
  if (!Array.isArray(value)) return [];
  return value.map(asJsonObject).filter((item) => Object.keys(item).length > 0);
}

function sources(value: unknown): RagSourceItem[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(normalizeRagSourceItem)
    .filter((source): source is RagSourceItem => source !== null);
}

function uniqueSourceUrls(
  urls: readonly string[],
  status: string,
): RagSourceItem[] {
  return [...new Set(urls)].map((url) => ({
    url,
    status,
    stage: status === "retrieved" ? "retrieved" : "search_result",
    documents: undefined,
    chunks: undefined,
    parser: undefined,
    error: null,
  }));
}

/** Normalize the many historical Web RAG result shapes into one UI model. */
export function normalizeSourceIndexingResult(
  value: unknown,
  statusType = "complete",
): SourceIndexingViewModel {
  const result = asJsonObject(value);
  const rag = asJsonObject(result.rag);
  const indexing = asJsonObject(result.indexing);
  const ragIndexing = asJsonObject(rag.indexing);
  const jobs = objects(result.jobs);
  const activeJob =
    jobs.find((job) =>
      ["queued", "running"].includes(String(job.status).toLowerCase()),
    ) ??
    jobs[0] ??
    {};
  const effective = Object.keys(indexing).length
    ? indexing
    : Object.keys(ragIndexing).length
      ? ragIndexing
      : activeJob;
  const parser = asJsonObject(effective.parser ?? result.parser);
  const indexStatus = asJsonObject(result.index_status ?? result.index);

  const retrievalSources = strings(rag.sources ?? result.sources);
  const searchResults = objects(result.results);
  const searchUrls = searchResults
    .map((item) => String(item.link ?? item.url ?? ""))
    .filter(Boolean);
  const documentRows = objects(result.documents).length
    ? objects(result.documents)
    : searchResults.slice(0, 5);

  return {
    indexerTool: String(effective.indexer_tool ?? "web_rag"),
    status: String(
      effective.status ?? (statusType === "running" ? "running" : "completed"),
    ),
    jobId: String(effective.job_id ?? ""),
    total: finiteNumber(
      effective.total_urls ?? effective.queued_urls ?? effective.total,
    ),
    completed: finiteNumber(effective.completed_urls ?? effective.completed),
    failed: finiteNumber(effective.failed_urls ?? effective.failed),
    parserName: String(parser.pdf_parser ?? "pypdf"),
    parserDevice: String(parser.docling_device ?? "cpu"),
    sources: sources(effective.sources ?? effective.items),
    retrievalSources,
    searchSources: uniqueSourceUrls(searchUrls, "discovered"),
    chunks: strings(rag.chunks ?? result.chunks),
    documents: documentRows.slice(0, 5).map((item) => ({
      title: String(item.title ?? "untitled"),
      snippet: String(item.snippet ?? ""),
      url: String(item.link ?? item.url ?? ""),
    })),
    indexedSourceCount:
      typeof indexStatus.source_count === "number"
        ? indexStatus.source_count
        : null,
    indexedDocumentCount:
      typeof indexStatus.document_count === "number"
        ? indexStatus.document_count
        : null,
  };
}

export function retrievalSourceItems(urls: readonly string[]): RagSourceItem[] {
  return uniqueSourceUrls(urls, "retrieved");
}
