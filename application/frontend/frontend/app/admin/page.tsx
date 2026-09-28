"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useApiClient } from "@/hooks/use-api-client";

type StatusResponse = {
  index?: Record<string, unknown>;
  jobs?: Array<Record<string, unknown>>;
};

type ToolsOverview = {
  tools?: Record<string, unknown>;
  runtime?: Record<string, unknown>;
  docling?: Record<string, unknown>;
};

export default function AdminPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [chunks, setChunks] = useState<any[]>([]);
  const [raw, setRaw] = useState<any[]>([]);
  const [query, setQuery] = useState("What is Elassona?");
  const [searchResult, setSearchResult] = useState<any>(null);
  const [overview, setOverview] = useState<ToolsOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const { config, loaded, client } = useApiClient();
  const ragEnabled = config.tools.web_rag.enabled;

  const refresh = async () => {
      setLoading(true);
      try {
        const [s, c, r] = await Promise.all([
        client.request<StatusResponse>("/tools/web_rag/status"),
        client.request<{ items?: unknown[] }>("/tools/web_rag/chunks?limit=20"),
        client.request<{ items?: unknown[] }>("/tools/web_rag/raw?limit=10"),
      ]);
      const o = await client.request<ToolsOverview>("/tools/overview");
      setStatus(s);
      setChunks(Array.isArray(c?.items) ? c.items : []);
      setRaw(Array.isArray(r?.items) ? r.items : []);
      setOverview(o);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Capability-gated: no polling when the backend does not serve RAG.
    if (!loaded || !ragEnabled) return;
    void refresh();
    const id = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(id);
  }, [loaded, ragEnabled, client]);

  const runTestSearch = async () => {
    const result = await client.request("/tools/web_rag/test-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, k: 5 }),
    });
    setSearchResult(result);
  };

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 text-sm">
      <header className="flex items-center justify-between border-b pb-3">
        <h1 className="text-lg font-semibold">Web RAG Admin</h1>
        <Link className="rounded border px-3 py-1" href="/">
          Back to chat
        </Link>
      </header>

      {loaded && !ragEnabled && (
        <section className="rounded border border-dashed p-3 text-xs text-muted-foreground">
          The Web RAG capability is disabled on this backend (see{" "}
          <code>/api/config</code>). Point this UI at the full backend to
          manage the index.
        </section>
      )}

      <section className="flex flex-wrap items-end gap-2">
        <button className="rounded border px-3 py-1" disabled={!ragEnabled} onClick={() => void refresh()}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </section>

      <section className="rounded border p-3">
        <h2 className="mb-2 font-semibold">Tools Overview</h2>
        <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(overview?.tools ?? {}, null, 2)}</pre>
      </section>

      <section className="rounded border p-3">
        <h2 className="mb-2 font-semibold">Runtime / Dependencies</h2>
        <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(overview?.runtime ?? {}, null, 2)}</pre>
      </section>

      <section className="rounded border p-3">
        <h2 className="mb-2 font-semibold">Docling Integration Info</h2>
        <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(overview?.docling ?? {}, null, 2)}</pre>
      </section>

      <section className="rounded border p-3">
        <h2 className="mb-2 font-semibold">Index Status</h2>
        <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(status?.index ?? {}, null, 2)}</pre>
      </section>

      <section className="rounded border p-3">
        <h2 className="mb-2 font-semibold">Background Jobs</h2>
        <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(status?.jobs ?? [], null, 2)}</pre>
      </section>

      <section className="rounded border p-3">
        <h2 className="mb-2 font-semibold">Raw Downloaded Sources (preview)</h2>
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">
          {JSON.stringify(raw, null, 2)}
        </pre>
      </section>

      <section className="rounded border p-3">
        <h2 className="mb-2 font-semibold">Indexed Chunks (preview)</h2>
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">
          {JSON.stringify(chunks, null, 2)}
        </pre>
      </section>

      <section className="rounded border p-3">
        <h2 className="mb-2 font-semibold">Test Search</h2>
        <div className="mb-2 flex gap-2">
          <input
            className="w-full rounded border px-2 py-1"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="rounded border px-3 py-1" onClick={() => void runTestSearch()}>
            Run
          </button>
        </div>
        <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(searchResult ?? {}, null, 2)}</pre>
      </section>
    </main>
  );
}
