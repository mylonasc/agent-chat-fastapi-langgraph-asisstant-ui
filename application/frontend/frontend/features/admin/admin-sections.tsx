"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApiClient } from "@/hooks/use-api-client";
import type { RagStatus, RagTestSearchResult } from "@/lib/api/types";

import type { JsonObject } from "./use-admin-rag";

function section(source: JsonObject | null, key: string): JsonObject {
  if (!source) return {};
  const value = source[key];
  return typeof value === "object" && value !== null
    ? (value as JsonObject)
    : {};
}

function JsonSection({ title, value }: { title: string; value: unknown }) {
  const empty =
    value === null ||
    value === undefined ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === "object" && Object.keys(value).length === 0);
  return (
    <section className="rounded border p-3">
      <h2 className="mb-2 font-semibold">{title}</h2>
      {empty ? (
        <p className="text-xs text-muted-foreground">No data available.</p>
      ) : (
        <pre className="max-h-64 overflow-auto text-xs whitespace-pre-wrap">
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
    </section>
  );
}

export function AdminOverview({ overview }: { overview: JsonObject | null }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <JsonSection title="Tools Overview" value={section(overview, "tools")} />
      <JsonSection
        title="Runtime / Dependencies"
        value={section(overview, "runtime")}
      />
      <JsonSection
        title="Docling Integration Info"
        value={section(overview, "docling")}
      />
    </div>
  );
}

export function AdminJobs({ status }: { status: RagStatus | null }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <JsonSection title="Index Status" value={status?.index ?? {}} />
      <JsonSection title="Background Jobs" value={status?.jobs ?? []} />
    </div>
  );
}

export function AdminSourcePreviews({
  raw,
  chunks,
}: {
  raw: JsonObject[];
  chunks: JsonObject[];
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <JsonSection title="Raw Downloaded Sources (preview)" value={raw} />
      <JsonSection title="Indexed Chunks (preview)" value={chunks} />
    </div>
  );
}

export function AdminTestSearch({ enabled }: { enabled: boolean }) {
  const { client } = useApiClient();
  const [query, setQuery] = useState("What is Elassona?");
  const [result, setResult] = useState<RagTestSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!enabled || !query.trim() || loading) return;
    setLoading(true);
    try {
      setResult(await client.rag.testSearch(query.trim(), 5));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Test search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded border p-3">
      <h2 className="mb-2 font-semibold">Test Search</h2>
      <div className="mb-2 flex gap-2">
        <Input
          aria-label="Test search query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void run();
          }}
        />
        <Button
          disabled={!enabled || !query.trim() || loading}
          onClick={() => void run()}
        >
          {loading ? "Running…" : "Run"}
        </Button>
      </div>
      {error && (
        <p role="alert" className="mb-2 text-xs text-destructive">
          {error}
        </p>
      )}
      {result ? (
        <pre className="max-h-64 overflow-auto text-xs whitespace-pre-wrap">
          {JSON.stringify(result, null, 2)}
        </pre>
      ) : (
        <p className="text-xs text-muted-foreground">
          Run a query to inspect retrieval results.
        </p>
      )}
    </section>
  );
}
