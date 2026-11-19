/**
 * Transport-independent error surface.
 *
 * `ApiError` keeps the HTTP status and backend error code so callers can make
 * behavioral decisions (e.g. 404 feedback means "not rated yet", 409 means
 * "already persisted") without re-parsing response payloads.
 */
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

/** A 2xx response whose body did not match the expected contract. */
export function malformedResponse(what: string): ApiError {
  return new ApiError(
    `Server returned an invalid ${what} payload`,
    200,
    "malformed_response",
  );
}

export function messageFromPayload(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null) return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail !== null) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return fallback;
}

export function codeFromPayload(payload: unknown): string | undefined {
  if (typeof payload !== "object" || payload === null) return undefined;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail !== "object" || detail === null) return undefined;
  const code = (detail as { error?: unknown }).error;
  return typeof code === "string" ? code : undefined;
}
