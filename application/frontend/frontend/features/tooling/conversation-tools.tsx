"use client";

import { useState } from "react";
import { useAssistantState } from "@assistant-ui/react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useApiClient } from "@/hooks/use-api-client";
import type { ToolSnapshot } from "@/lib/api/services/tooling";
import { ToolSettingsForm } from "./tool-settings-form";

export function ConversationTools() {
  const { client, config } = useApiClient();
  const threadId = useAssistantState((state) => state.threadListItem?.remoteId);
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<{
    id: string;
    snapshot: ToolSnapshot;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  if (!config.tooling?.enabled) return null;
  const load = async () => {
    if (!threadId) return;
    setError(null);
    setData(null);
    setSaved(false);
    try {
      setData({
        id: threadId,
        snapshot: await client.tooling.thread(threadId),
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load tools");
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        setOpen(value);
        if (value) void load();
      }}
    >
      <Button
        variant="outline"
        size="sm"
        disabled={!threadId}
        onClick={() => {
          setOpen(true);
          void load();
        }}
      >
        Conversation tools
      </Button>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-3xl">
        <DialogTitle>Conversation tools</DialogTitle>
        <DialogDescription>
          Enable tools and adjust their settings for this conversation.
        </DialogDescription>
        {error && <p role="alert">{error}</p>}
        <Button variant="outline" size="sm" onClick={() => void load()}>
          Refresh settings
        </Button>
        {data && data.id === threadId && (
          <ToolSettingsForm
            key={`${threadId}-${data.snapshot.revision}-${data.snapshot.global_revision}`}
            snapshot={data.snapshot}
            onSave={async (body) => {
              const snapshot = await client.tooling.saveThread(data.id, body);
              setData({ id: data.id, snapshot });
              setSaved(true);
            }}
          />
        )}
        {saved && (
          <p role="status">Tool settings saved. They apply to the next turn.</p>
        )}
        {!data && !error && <p role="status">Loading tools…</p>}
      </DialogContent>
    </Dialog>
  );
}
