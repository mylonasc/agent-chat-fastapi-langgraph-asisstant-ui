/**
 * Application API facade.
 *
 * `ApiClient` composes typed domain services and is the single object handed
 * to the component tree. Components never build endpoint paths or parse raw
 * responses; they call `client.threads`, `client.transcripts`, etc.
 */
import type { ClientIdentity } from "@/lib/identity";

import { HttpTransport } from "./api/transport";
import { AgentsService } from "./api/services/agents";
import { FeedbackService } from "./api/services/feedback";
import { RagService } from "./api/services/rag";
import { TranscriptsService } from "./api/services/transcripts";
import { ThreadsService } from "./api/services/threads";

export { ApiError } from "./api/errors";
export type {
  AgentListing,
  ChatTranscript,
  ChatTranscriptMessage,
  FeedbackRating,
  MessageFeedback,
  RagIndexStats,
  RagJob,
  RagPage,
  RagSourceItem,
  RagStatus,
  ThreadMetadata,
} from "./api/types";

export class ApiClient {
  private readonly transport: HttpTransport;

  readonly threads: ThreadsService;
  readonly transcripts: TranscriptsService;
  readonly feedback: FeedbackService;
  readonly agents: AgentsService;
  readonly rag: RagService;

  constructor(
    readonly apiBase: string,
    readonly identity: ClientIdentity,
  ) {
    this.transport = new HttpTransport(apiBase, identity);
    this.threads = new ThreadsService(this.transport);
    this.transcripts = new TranscriptsService(this.transport);
    this.feedback = new FeedbackService(this.transport);
    this.agents = new AgentsService(this.transport);
    this.rag = new RagService(this.transport);
  }

  headers(extra?: HeadersInit): Headers {
    return this.transport.headers(extra);
  }

  assistantUrl(): string {
    return this.transport.url("/assistant");
  }
}
