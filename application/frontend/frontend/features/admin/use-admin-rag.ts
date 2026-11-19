"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useApiClient } from "@/hooks/use-api-client";

import { useRagStatusPolling } from "../rag/use-rag-status-polling";

export type JsonObject = Record<string, unknown>;

function message(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Failed to load Web RAG administration data";
}

/** Admin data orchestration with non-overlapping details requests. */
export function useAdminRag() {
  const { config, loaded, client } = useApiClient();
  const adminEnabled = config.tools.admin.enabled;
  const ragEnabled = config.tools.web_rag.enabled;
  const ready = loaded && adminEnabled && ragEnabled;
  const statusPolling = useRagStatusPolling({
    enabled: ready,
    intervalMs: 2000,
  });
  const [chunks, setChunks] = useState<JsonObject[]>([]);
  const [raw, setRaw] = useState<JsonObject[]>([]);
  const [overview, setOverview] = useState<JsonObject | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const detailsActive = useRef(false);

  const refreshDetails = useCallback(async () => {
    if (!ready || detailsActive.current) return;
    detailsActive.current = true;
    setDetailsLoading(true);
    try {
      const [nextChunks, nextRaw, nextOverview] = await Promise.all([
        client.rag.chunks(20),
        client.rag.raw(10),
        client.rag.overview(),
      ]);
      setChunks(nextChunks.items);
      setRaw(nextRaw.items);
      setOverview(nextOverview);
      setDetailsError(null);
    } catch (error) {
      setDetailsError(message(error));
    } finally {
      detailsActive.current = false;
      setDetailsLoading(false);
    }
  }, [client, ready]);

  useEffect(() => {
    void refreshDetails();
  }, [refreshDetails]);

  const refresh = useCallback(async () => {
    await Promise.all([statusPolling.refresh(), refreshDetails()]);
  }, [refreshDetails, statusPolling]);

  return {
    loaded,
    adminEnabled,
    ragEnabled,
    ready,
    status: statusPolling.data,
    chunks,
    raw,
    overview,
    loading: statusPolling.loading || detailsLoading,
    error: statusPolling.error ?? detailsError,
    refresh,
  };
}
