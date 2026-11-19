import { normalizeFeedback } from "@/lib/api/normalize";
import type { FeedbackRating, MessageFeedback } from "@/lib/api/types";
import type { HttpTransport } from "@/lib/api/transport";

function feedbackPath(threadId: string, messageId: string): string {
  return `/threads/${encodeURIComponent(threadId)}/messages/${encodeURIComponent(messageId)}/feedback`;
}

/** Per-message rating endpoints (idempotent upsert + retraction). */
export class FeedbackService {
  constructor(private readonly transport: HttpTransport) {}

  async get(threadId: string, messageId: string): Promise<MessageFeedback> {
    return normalizeFeedback(
      await this.transport.request<unknown>(feedbackPath(threadId, messageId)),
    );
  }

  async upsert(
    threadId: string,
    messageId: string,
    rating: FeedbackRating,
  ): Promise<MessageFeedback> {
    return normalizeFeedback(
      await this.transport.request<unknown>(feedbackPath(threadId, messageId), {
        method: "PUT",
        body: { rating },
      }),
    );
  }

  async remove(threadId: string, messageId: string): Promise<void> {
    await this.transport.request<unknown>(feedbackPath(threadId, messageId), {
      method: "DELETE",
    });
  }
}
