/**
 * Runtime validation for boundary payloads.
 *
 * Every helper treats its input as `unknown`. Top-level shape violations throw
 * an `ApiError` (surfaced by the existing UI error paths) instead of leaking a
 * malformed value into React; individual malformed list entries are skipped so
 * one bad row cannot blank an otherwise usable view.
 */
import { malformedResponse } from "./errors";
import type {
  AgentListing,
  ChatTranscript,
  ChatTranscriptMessage,
  MessageFeedback,
  RagIndexStats,
  RagJob,
  RagPage,
  RagSourceItem,
  RagStatus,
  ThreadMetadata,
} from "./types";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function record(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

export function stringOr(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

export function optionalString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

export function numberOr(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

export function booleanOr(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

export function normalizeThread(value: unknown): ThreadMetadata | null {
  if (!isRecord(value)) return null;
  const id = optionalString(value.id);
  if (!id) return null;
  return {
    id,
    title: stringOr(value.title, "New Chat"),
    is_archived: booleanOr(value.is_archived, false),
    user_id: stringOr(value.user_id, ""),
  };
}

export function normalizeThreadList(payload: unknown): ThreadMetadata[] {
  if (!Array.isArray(payload)) throw malformedResponse("thread list");
  return payload
    .map(normalizeThread)
    .filter((thread): thread is ThreadMetadata => thread !== null);
}

export function normalizeThreadResponse(payload: unknown): ThreadMetadata {
  const thread = normalizeThread(payload);
  if (!thread) throw malformedResponse("thread");
  return thread;
}

export function normalizeTranscriptMessage(
  value: unknown,
): ChatTranscriptMessage | null {
  if (!isRecord(value)) return null;
  const message: ChatTranscriptMessage = { ...value };
  if (typeof value.id !== "string") delete message.id;
  return message;
}

export function normalizeTranscript(payload: unknown): ChatTranscript {
  if (!isRecord(payload) || !Array.isArray(payload.messages)) {
    throw malformedResponse("transcript");
  }
  return {
    messages: payload.messages
      .map(normalizeTranscriptMessage)
      .filter((message): message is ChatTranscriptMessage => message !== null),
  };
}

export function normalizeFeedback(payload: unknown): MessageFeedback {
  if (!isRecord(payload)) throw malformedResponse("feedback");
  const rating = payload.rating;
  if (rating !== "positive" && rating !== "negative") {
    throw malformedResponse("feedback");
  }
  return {
    id: stringOr(payload.id, ""),
    thread_id: stringOr(payload.thread_id, ""),
    message_id: stringOr(payload.message_id, ""),
    rating,
    comment: typeof payload.comment === "string" ? payload.comment : null,
    metadata: record(payload.metadata),
    created_at: stringOr(payload.created_at, ""),
    updated_at: stringOr(payload.updated_at, ""),
  };
}

export function normalizeAgents(payload: unknown): AgentListing {
  if (!isRecord(payload)) throw malformedResponse("agent list");
  const agents = Array.isArray(payload.agents)
    ? payload.agents.filter(
        (agent): agent is string => typeof agent === "string",
      )
    : [];
  const fallback = typeof payload.default === "string" ? payload.default : null;
  return { agents, default: fallback };
}

export function normalizeRagSourceItem(value: unknown): RagSourceItem | null {
  if (!isRecord(value)) return null;
  const url = stringOr(value.url, "");
  if (!url) return null;
  return {
    url,
    status: stringOr(value.status, "queued"),
    stage: optionalString(value.stage),
    chunks: optionalNumber(value.chunks),
    documents: optionalNumber(value.documents),
    parser: optionalString(value.parser),
    error: typeof value.error === "string" ? value.error : null,
  };
}

export function normalizeRagIndexStats(value: unknown): RagIndexStats {
  const data = record(value);
  return {
    user_id: optionalString(data.user_id),
    base_path: optionalString(data.base_path),
    document_count: optionalNumber(data.document_count),
    source_count: optionalNumber(data.source_count),
    has_faiss: typeof data.has_faiss === "boolean" ? data.has_faiss : undefined,
    has_bm25: typeof data.has_bm25 === "boolean" ? data.has_bm25 : undefined,
    raw_sources_count: optionalNumber(data.raw_sources_count),
    is_empty: typeof data.is_empty === "boolean" ? data.is_empty : undefined,
  };
}

export function normalizeRagJob(value: unknown): RagJob | null {
  if (!isRecord(value)) return null;
  const jobId = optionalString(value.job_id);
  if (!jobId) return null;
  const rawItems = Array.isArray(value.items)
    ? value.items
    : Array.isArray(value.sources)
      ? value.sources
      : [];
  return {
    job_id: jobId,
    status: stringOr(value.status, "queued"),
    indexer_tool: optionalString(value.indexer_tool),
    total_urls: optionalNumber(value.total_urls),
    completed_urls: optionalNumber(value.completed_urls),
    failed_urls: optionalNumber(value.failed_urls),
    items: rawItems
      .map(normalizeRagSourceItem)
      .filter((item): item is RagSourceItem => item !== null),
  };
}

export function normalizeRagStatus(payload: unknown): RagStatus {
  if (!isRecord(payload)) throw malformedResponse("index status");
  const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
  return {
    index: normalizeRagIndexStats(payload.index),
    jobs: jobs
      .map(normalizeRagJob)
      .filter((job): job is RagJob => job !== null),
  };
}

export function normalizeRagPage(
  payload: unknown,
): RagPage<Record<string, unknown>> {
  if (!isRecord(payload) || !Array.isArray(payload.items)) {
    throw malformedResponse("index page");
  }
  const items = payload.items.filter(isRecord);
  return {
    total: numberOr(payload.total, items.length),
    offset: numberOr(payload.offset, 0),
    limit: numberOr(payload.limit, items.length),
    items,
  };
}

/** Overview is diagnostic JSON; keep unknown keys but guarantee an object. */
export function normalizeRagOverview(
  payload: unknown,
): Record<string, unknown> {
  if (!isRecord(payload)) throw malformedResponse("tools overview");
  return payload;
}

/** A tool search result is displayed verbatim; only the envelope is trusted. */
export function normalizeRagTestSearch(
  payload: unknown,
): Record<string, unknown> {
  if (!isRecord(payload)) throw malformedResponse("search result");
  return payload;
}
