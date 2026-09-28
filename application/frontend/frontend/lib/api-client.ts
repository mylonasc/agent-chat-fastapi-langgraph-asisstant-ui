import { identityHeaders, type ClientIdentity } from "@/lib/identity";

export interface ThreadMetadata {
  id: string;
  title: string;
  is_archived: boolean;
  user_id: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function messageFromPayload(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null) return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail !== null) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return fallback;
}

function codeFromPayload(payload: unknown): string | undefined {
  if (typeof payload !== "object" || payload === null) return undefined;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail !== "object" || detail === null) return undefined;
  const code = (detail as { error?: unknown }).error;
  return typeof code === "string" ? code : undefined;
}

export class ApiClient {
  constructor(
    readonly apiBase: string,
    readonly identity: ClientIdentity,
  ) {}

  headers(extra?: HeadersInit): Headers {
    const headers = new Headers(extra);
    for (const [name, value] of Object.entries(identityHeaders(this.identity))) {
      headers.set(name, value);
    }
    return headers;
  }

  assistantUrl(): string {
    return `${this.apiBase}/assistant`;
  }

  async request<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    const response = await fetch(`${this.apiBase}${path}`, {
      ...options,
      headers: this.headers(options.headers),
      cache: options.cache ?? "no-store",
    });
    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        if (response.ok) {
          throw new ApiError("Server returned malformed JSON", response.status);
        }
      }
    }
    if (!response.ok) {
      throw new ApiError(
        messageFromPayload(payload, `Request failed (${response.status})`),
        response.status,
        codeFromPayload(payload),
      );
    }
    return payload as T;
  }

  listThreads(): Promise<ThreadMetadata[]> {
    return this.request("/threads");
  }

  getThread(threadId: string): Promise<ThreadMetadata> {
    return this.request(`/threads/${encodeURIComponent(threadId)}`);
  }

  createThread(localId: string, title = "New Chat"): Promise<ThreadMetadata> {
    return this.request("/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ localId, title }),
    });
  }

  renameThread(threadId: string, title: string): Promise<ThreadMetadata> {
    return this.request(`/threads/${encodeURIComponent(threadId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
  }

  archiveThread(threadId: string, archived: boolean): Promise<ThreadMetadata> {
    return this.request(
      `/threads/${encodeURIComponent(threadId)}/${archived ? "archive" : "unarchive"}`,
      { method: "POST" },
    );
  }

  async deleteThread(threadId: string): Promise<void> {
    await this.request(`/threads/${encodeURIComponent(threadId)}`, {
      method: "DELETE",
    });
  }

  getMessages(threadId: string): Promise<{ messages: unknown[] }> {
    return this.request(`/threads/${encodeURIComponent(threadId)}/messages`);
  }

  toolUrl(path: string): string {
    return `${this.apiBase}${path}`;
  }
}
