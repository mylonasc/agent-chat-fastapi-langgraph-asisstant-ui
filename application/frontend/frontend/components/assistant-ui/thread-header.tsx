"use client";

import { useAssistantApi, useAssistantState } from "@assistant-ui/react";
import type { FC } from "react";

import { HeaderActionHost } from "@/features/registry/registry-hosts";
import { useApiClient } from "@/hooks/use-api-client";

const ChatTitle: FC = () => {
  const api = useAssistantApi();
  const title = useAssistantState(
    (state) => state.threadListItem.title ?? "New Chat",
  );

  const rename = () => {
    const next = window.prompt("Rename chat", title);
    if (next == null) return;
    const cleaned = cleanTitle(next);
    if (!cleaned || cleaned === title) return;
    api.threadListItem().rename(cleaned);
  };

  return (
    <button
      type="button"
      onClick={rename}
      className="min-h-6 text-sm font-medium hover:underline"
      title="Rename chat"
    >
      {title}
    </button>
  );
};

function cleanTitle(input: string): string {
  const compact = input.replace(/\s+/g, " ").trim();
  const stripped = compact.replace(/^[-:.,\s]+|[-:.,\s]+$/g, "");
  return stripped.slice(0, 64);
}

/** Thread title and capability-gated header actions. */
export const ThreadHeader: FC = () => {
  const { config } = useApiClient();
  return (
    <div className="flex items-center justify-between border-b px-4 py-2">
      {config.features.threads ? (
        <ChatTitle />
      ) : (
        <span className="text-sm font-medium">{config.presentation.title}</span>
      )}
      <HeaderActionHost />
    </div>
  );
};
