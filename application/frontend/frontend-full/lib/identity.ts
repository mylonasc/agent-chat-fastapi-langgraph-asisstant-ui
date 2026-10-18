"use client";

/**
 * Browser identity for the legacy full UI.
 *
 * Mirrors the unified frontend (`frontend/lib/identity.ts`): a stable
 * anonymous subject per browser, sent as `x-agent-chat-subject` so the
 * packaged app can enforce ownership (#62). The same subject doubles as
 * the legacy `user_id` namespace for the full backend, which has no
 * principal concept. Shares the storage key with the unified UI so one
 * browser keeps one subject across both frontends.
 */

export const ANONYMOUS_SUBJECT_STORAGE_KEY = "agent-chat.anonymous-subject.v1";

/** Fallback only when no browser storage is available (SSR). */
export const FALLBACK_SUBJECT = "default_user";

export interface ClientIdentity {
  subject: string | null;
  headers?: Record<string, string>;
}

function newAnonymousSubject(): string {
  const suffix =
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `anon-${suffix}`;
}

export function getOrCreateAnonymousSubject(storage: Storage): string {
  const saved = storage.getItem(ANONYMOUS_SUBJECT_STORAGE_KEY);
  if (saved?.trim()) return saved;
  const subject = newAnonymousSubject();
  storage.setItem(ANONYMOUS_SUBJECT_STORAGE_KEY, subject);
  return subject;
}

/** Resolve the browser subject; never throws, falls back for SSR. */
export function resolveBrowserSubject(): string {
  if (typeof window === "undefined") return FALLBACK_SUBJECT;
  try {
    return getOrCreateAnonymousSubject(window.localStorage);
  } catch {
    return FALLBACK_SUBJECT;
  }
}

export function identityHeaders(
  identity: ClientIdentity,
): Record<string, string> {
  return {
    ...(identity.headers ?? {}),
    ...(identity.subject ? { "x-agent-chat-subject": identity.subject } : {}),
  };
}
