"use client";

import { useAssistantApi, useAssistantState } from "@assistant-ui/react";
import { useEffect, useRef, type FC } from "react";

import { useApiClient } from "@/hooks/use-api-client";
import type { ThreadMessage } from "@/lib/assistant/runtime-compat";

const AUTO_TITLE_DEFAULTS = ["", "New Chat", "Untitled"] as const;

function isDefaultTitle(title: string): boolean {
  return (AUTO_TITLE_DEFAULTS as readonly string[]).includes(title);
}

function cleanTitle(input: string): string {
  const compact = input.replace(/\s+/g, " ").trim();
  const stripped = compact.replace(/^[-:.,\s]+|[-:.,\s]+$/g, "");
  return stripped.slice(0, 64);
}

function textOf(message: ThreadMessage): string {
  return message.content
    .map((part) => (part.type === "text" ? part.text : ""))
    .join(" ");
}

function deriveThreadTitle(messages: readonly ThreadMessage[]): string | null {
  const userMessages = messages.filter((message) => message.role === "user");
  const assistantMessages = messages.filter(
    (message) => message.role === "assistant",
  );

  // Title the chat as soon as the first response arrives: one user turn to
  // derive from plus one assistant turn proving the exchange completed.
  // (An LLM-provided name can replace this heuristic later; the rename path
  // it will use — threadListItem().rename() — stays the same.)
  if (userMessages.length < 1 || assistantMessages.length < 1) {
    return null;
  }

  const cleaned = cleanTitle(userMessages.map(textOf).join(" "));
  return cleaned || null;
}

/**
 * Titles a never-renamed thread from its first completed exchange.
 *
 * The per-mount ref only prevents duplicate renames within one mount; the
 * backend rename itself is idempotent for an unchanged title.
 */
export const AutoThreadTitle: FC = () => {
  const api = useAssistantApi();
  const { config } = useApiClient();
  const threadItem = useAssistantState((state) => state.threadListItem);
  const messages = useAssistantState((state) => state.thread.messages);
  const autoTitledByThreadRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    // Thread titles only exist for thread-list deployments.
    if (!config.features.threads) return;
    const threadId = threadItem?.remoteId ?? threadItem?.id;
    const currentTitle = String(threadItem?.title ?? "");

    if (!threadId) return;
    if (!isDefaultTitle(currentTitle)) return;
    if (autoTitledByThreadRef.current.has(threadId)) return;

    const suggested = deriveThreadTitle(messages);
    if (!suggested || isDefaultTitle(suggested)) return;

    autoTitledByThreadRef.current.add(threadId);
    api.threadListItem().rename(suggested);
  }, [
    api,
    config.features.threads,
    messages,
    threadItem?.id,
    threadItem?.remoteId,
    threadItem?.title,
  ]);

  return null;
};
