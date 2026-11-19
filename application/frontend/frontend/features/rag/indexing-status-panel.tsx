"use client";

import type { FC } from "react";

import {
  hasActiveRagJobs,
  useRagStatusPolling,
} from "./use-rag-status-polling";

/** Active indexing jobs shown under the transcript while RAG is running. */
export const IndexingStatusPanel: FC = () => {
  const { data } = useRagStatusPolling({ continueWhile: hasActiveRagJobs });
  const jobs =
    data?.jobs.filter((job) =>
      ["queued", "running"].includes(job.status.toLowerCase()),
    ) ?? [];

  if (!jobs.length) return null;

  return (
    <div className="mx-auto mt-2 w-full max-w-[var(--thread-max-width)] px-2">
      <div className="rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
        {jobs.map((job) => (
          <div key={job.job_id} className="mb-1 last:mb-0">
            Indexing {job.completed_urls ?? 0}/{job.total_urls ?? 0}
            {job.failed_urls ? ` (${job.failed_urls} failed)` : ""} -{" "}
            {job.status}
          </div>
        ))}
      </div>
    </div>
  );
};
