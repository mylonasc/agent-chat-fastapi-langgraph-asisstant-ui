import {
  normalizeThreadList,
  normalizeThreadResponse,
} from "@/lib/api/normalize";
import type { ThreadMetadata } from "@/lib/api/types";
import type { HttpTransport } from "@/lib/api/transport";

/** Thread lifecycle endpoints used by the remote thread-list adapter. */
export class ThreadsService {
  constructor(private readonly transport: HttpTransport) {}

  async list(): Promise<ThreadMetadata[]> {
    return normalizeThreadList(
      await this.transport.request<unknown>("/threads"),
    );
  }

  async get(threadId: string): Promise<ThreadMetadata> {
    return normalizeThreadResponse(
      await this.transport.request<unknown>(
        `/threads/${encodeURIComponent(threadId)}`,
      ),
    );
  }

  async create(localId: string, title = "New Chat"): Promise<ThreadMetadata> {
    return normalizeThreadResponse(
      await this.transport.request<unknown>("/threads", {
        method: "POST",
        body: { localId, title },
      }),
    );
  }

  async rename(threadId: string, title: string): Promise<ThreadMetadata> {
    return normalizeThreadResponse(
      await this.transport.request<unknown>(
        `/threads/${encodeURIComponent(threadId)}`,
        { method: "PATCH", body: { title } },
      ),
    );
  }

  async setArchived(
    threadId: string,
    archived: boolean,
  ): Promise<ThreadMetadata> {
    return normalizeThreadResponse(
      await this.transport.request<unknown>(
        `/threads/${encodeURIComponent(threadId)}/${archived ? "archive" : "unarchive"}`,
        { method: "POST" },
      ),
    );
  }

  async delete(threadId: string): Promise<void> {
    await this.transport.request<unknown>(
      `/threads/${encodeURIComponent(threadId)}`,
      { method: "DELETE" },
    );
  }
}
