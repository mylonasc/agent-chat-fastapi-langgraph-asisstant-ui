"use client";

import { useMemo } from "react";
import {
  A2UIProvider,
  A2UIRenderer,
  type A2UIAction,
  type A2UIMessage,
} from "@a2ui-sdk/react/0.9";
import { customCatalog } from "./a2ui-catalog";

function parseMessages(result: unknown): A2UIMessage[] | null {
  let payload: unknown = result;
  if (typeof payload === "string") {
    try {
      payload = JSON.parse(payload);
    } catch {
      return null;
    }
  }
  if (!payload || typeof payload !== "object") return null;
  const messages = (payload as { messages?: unknown }).messages;
  if (!Array.isArray(messages) || messages.length === 0) return null;
  if (!messages.every((m) => m && typeof m === "object")) return null;
  return messages as A2UIMessage[];
}

export function isA2UIResult(result: unknown): boolean {
  return parseMessages(result) !== null;
}

export function A2UISurface({
  result,
  onAction,
}: {
  result: unknown;
  onAction: (action: A2UIAction) => void;
}) {
  const messages = useMemo(() => parseMessages(result) ?? [], [result]);
  if (messages.length === 0) return null;
  return (
    <div className="mb-4 w-full overflow-hidden rounded-2xl border bg-background shadow-sm">
      <A2UIProvider messages={messages} catalog={customCatalog}>
        <A2UIRenderer onAction={onAction} />
      </A2UIProvider>
    </div>
  );
}
