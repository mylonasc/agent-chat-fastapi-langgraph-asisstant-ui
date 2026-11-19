import { normalizeTranscript } from "@/lib/api/normalize";
import type { ChatTranscript } from "@/lib/api/types";
import type { HttpTransport } from "@/lib/api/transport";

/** Stored assistant-ui transcripts used for reload hydration and durability. */
export class TranscriptsService {
  constructor(private readonly transport: HttpTransport) {}

  async list(threadId: string): Promise<ChatTranscript> {
    return normalizeTranscript(
      await this.transport.request<unknown>(
        `/threads/${encodeURIComponent(threadId)}/messages`,
      ),
    );
  }

  async append(threadId: string, message: unknown): Promise<void> {
    await this.transport.request<unknown>(
      `/threads/${encodeURIComponent(threadId)}/messages`,
      { method: "POST", body: { message } },
    );
  }
}
