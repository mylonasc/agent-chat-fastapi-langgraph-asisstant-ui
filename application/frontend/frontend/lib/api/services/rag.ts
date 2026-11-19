import {
  normalizeRagOverview,
  normalizeRagPage,
  normalizeRagStatus,
  normalizeRagTestSearch,
} from "@/lib/api/normalize";
import type { RagPage, RagStatus, RagTestSearchResult } from "@/lib/api/types";
import type { HttpTransport } from "@/lib/api/transport";

/** Default status path, mirrored by the packaged runtime config. */
export const DEFAULT_RAG_STATUS_PATH = "/tools/web_rag/status";

function query(params: Record<string, number>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    search.set(key, String(value));
  }
  return search.toString();
}

/** Web RAG administration and status endpoints. */
export class RagService {
  constructor(private readonly transport: HttpTransport) {}

  async status(
    statusPath: string | null = DEFAULT_RAG_STATUS_PATH,
  ): Promise<RagStatus> {
    const path = statusPath ?? DEFAULT_RAG_STATUS_PATH;
    return normalizeRagStatus(await this.transport.request<unknown>(path));
  }

  async overview(): Promise<Record<string, unknown>> {
    return normalizeRagOverview(
      await this.transport.request<unknown>("/tools/overview"),
    );
  }

  async chunks(
    limit = 20,
    offset = 0,
  ): Promise<RagPage<Record<string, unknown>>> {
    return normalizeRagPage(
      await this.transport.request<unknown>(
        `/tools/web_rag/chunks?${query({ limit, offset })}`,
      ),
    );
  }

  async raw(limit = 10, offset = 0): Promise<RagPage<Record<string, unknown>>> {
    return normalizeRagPage(
      await this.transport.request<unknown>(
        `/tools/web_rag/raw?${query({ limit, offset })}`,
      ),
    );
  }

  async testSearch(queryText: string, k = 5): Promise<RagTestSearchResult> {
    return normalizeRagTestSearch(
      await this.transport.request<unknown>("/tools/web_rag/test-search", {
        method: "POST",
        body: { query: queryText, k },
      }),
    );
  }
}
