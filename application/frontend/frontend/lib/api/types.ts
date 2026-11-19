/**
 * Shared transport DTOs.
 *
 * These describe the wire contract between the UI and the chat backend. They
 * intentionally stay close to the JSON shapes so services can normalize
 * untrusted payloads before React components see them.
 */

export interface ThreadMetadata {
  id: string;
  title: string;
  is_archived: boolean;
  user_id: string;
}

export type FeedbackRating = "positive" | "negative";

export interface MessageFeedback {
  id: string;
  thread_id: string;
  message_id: string;
  rating: FeedbackRating;
  comment: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** A verbatim assistant-ui message payload stored by the transcript endpoint. */
export type ChatTranscriptMessage = Record<string, unknown> & {
  id?: string;
  role?: string;
  content?: unknown;
};

export interface ChatTranscript {
  messages: ChatTranscriptMessage[];
}

export interface AgentListing {
  agents: string[];
  default: string | null;
}

export interface RagIndexStats {
  user_id?: string;
  base_path?: string;
  document_count?: number;
  source_count?: number;
  has_faiss?: boolean;
  has_bm25?: boolean;
  raw_sources_count?: number;
  is_empty?: boolean;
}

export interface RagSourceItem {
  url: string;
  status: string;
  stage?: string;
  chunks?: number;
  documents?: number;
  parser?: string;
  error?: string | null;
}

export interface RagJob {
  job_id: string;
  status: string;
  indexer_tool?: string;
  total_urls?: number;
  completed_urls?: number;
  failed_urls?: number;
  items: RagSourceItem[];
}

export interface RagStatus {
  index: RagIndexStats;
  jobs: RagJob[];
}

export interface RagPage<T> {
  total: number;
  offset: number;
  limit: number;
  items: T[];
}

export type RagOverview = Record<string, unknown>;

export type RagTestSearchResult = Record<string, unknown>;
