"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useApiClient } from "@/hooks/use-api-client";
import type { RagStatus } from "@/lib/api/types";

export interface RagStatusPollingOptions {
  enabled?: boolean;
  intervalMs?: number;
  continueWhile?: (status: RagStatus) => boolean;
}

/**
 * Non-overlapping, visibility-aware polling shared by tool, transcript, and
 * admin views. A new timer is scheduled only after the previous request has
 * settled. Hidden pages pause and resume with one immediate refresh.
 */
export function useRagStatusPolling({
  enabled = true,
  intervalMs = 1200,
  continueWhile = () => true,
}: RagStatusPollingOptions = {}) {
  const { config, client } = useApiClient();
  const capability = config.tools.web_rag;
  const [data, setData] = useState<RagStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<number | null>(null);
  const activeRef = useRef(false);
  const continueRef = useRef(continueWhile);
  continueRef.current = continueWhile;

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const refresh = useCallback(async (): Promise<RagStatus | null> => {
    if (
      !enabled ||
      !capability.enabled ||
      capability.status_path === null ||
      activeRef.current
    ) {
      return null;
    }
    activeRef.current = true;
    setLoading(true);
    try {
      const next = await client.rag.status(capability.status_path);
      setData(next);
      setError(null);
      return next;
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load RAG status",
      );
      return null;
    } finally {
      activeRef.current = false;
      setLoading(false);
    }
  }, [capability.enabled, capability.status_path, client, enabled]);

  useEffect(() => {
    if (!enabled || !capability.enabled || capability.status_path === null)
      return;
    let cancelled = false;

    const run = async () => {
      clearTimer();
      if (document.visibilityState === "hidden") return;
      const next = await refresh();
      if (
        !cancelled &&
        next &&
        continueRef.current(next) &&
        document.visibilityState === "visible"
      ) {
        timerRef.current = window.setTimeout(run, intervalMs);
      }
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") void run();
      else clearTimer();
    };

    document.addEventListener("visibilitychange", onVisibility);
    void run();
    return () => {
      cancelled = true;
      clearTimer();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [
    capability.enabled,
    capability.status_path,
    clearTimer,
    enabled,
    intervalMs,
    refresh,
  ]);

  return { data, error, loading, refresh };
}

export function hasActiveRagJobs(status: RagStatus): boolean {
  return status.jobs.some((job) =>
    ["queued", "running"].includes(job.status.toLowerCase()),
  );
}
