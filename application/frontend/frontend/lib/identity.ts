"use client";

import { useEffect, useState } from "react";

import type { IdentityMode } from "@/lib/runtime-config";

export const ANONYMOUS_SUBJECT_STORAGE_KEY = "agent-chat.anonymous-subject.v1";

export interface ClientIdentity {
  /** Trusted by the server only after its PrincipalResolver validates it. */
  subject: string | null;
  /** Extra auth headers supplied by an embedding application in delegated mode. */
  headers?: Record<string, string>;
}

/**
 * Extension point for an authenticated embedding. Set this before loading the
 * UI, or pass an identity through a future embedding-specific provider. The
 * bundled UI never interprets a token; it forwards opaque headers only.
 */
declare global {
  interface Window {
    agentChatIdentity?: ClientIdentity;
  }
}

function newAnonymousSubject(): string {
  const suffix =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
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

/** Resolve the browser identity without accepting any tool/body user_id. */
export function useClientIdentity(mode: IdentityMode): ClientIdentity {
  const [identity, setIdentity] = useState<ClientIdentity>({ subject: null });

  useEffect(() => {
    if (mode === "delegated") {
      setIdentity(window.agentChatIdentity ?? { subject: null });
      return;
    }
    setIdentity({ subject: getOrCreateAnonymousSubject(window.localStorage) });
  }, [mode]);

  return identity;
}

export function identityHeaders(identity: ClientIdentity): Record<string, string> {
  return {
    ...(identity.headers ?? {}),
    ...(identity.subject ? { "x-agent-chat-subject": identity.subject } : {}),
  };
}
