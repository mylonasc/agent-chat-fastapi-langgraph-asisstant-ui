/**
 * HTTP transport for the application API.
 *
 * This is the only module that knows how to talk to the backend. Domain
 * services own endpoint paths; React components only call domain methods.
 */
import { identityHeaders, type ClientIdentity } from "@/lib/identity";

import { ApiError, codeFromPayload, messageFromPayload } from "./errors";

export interface TransportRequest {
  method?: string;
  body?: unknown;
  headers?: HeadersInit;
  cache?: RequestCache;
}

export class HttpTransport {
  constructor(
    readonly apiBase: string,
    readonly identity: ClientIdentity,
  ) {}

  headers(extra?: HeadersInit): Headers {
    const headers = new Headers(extra);
    for (const [name, value] of Object.entries(
      identityHeaders(this.identity),
    )) {
      headers.set(name, value);
    }
    return headers;
  }

  url(path: string): string {
    return `${this.apiBase}${path}`;
  }

  /** JSON request that preserves HTTP status and backend error codes. */
  async request<T>(path: string, options: TransportRequest = {}): Promise<T> {
    const headers = this.headers(options.headers);
    const init: RequestInit = { headers, cache: options.cache ?? "no-store" };
    init.method = options.method ?? "GET";
    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
      init.body = JSON.stringify(options.body);
    }

    const response = await fetch(this.url(path), init);
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
}
