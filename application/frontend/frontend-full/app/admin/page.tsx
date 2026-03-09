"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/assistant$/, "") ??
  "http://localhost:8010";

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
  const [userId, setUserId] = useState("default_user");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [chunks, setChunks] = useState<any[]>([]);
  const [raw, setRaw] = useState<any[]>([]);
  const [query, setQuery] = useState("What is Elassona?");
  const [searchResult, setSearchResult] = useState<any>(null);
  const [overview, setOverview] = useState<ToolsOverview | null>(null);
  const [loading, setLoading] = useState(false);

  const chunksUrl = useMemo(
    () => `${API_BASE}/tools/web_rag/chunks?user_id=${encodeURIComponent(userId)}&limit=20`,
    [userId]
  );
  const rawUrl = useMemo(
    () => `${API_BASE}/tools/web_rag/raw?user_id=${encodeURIComponent(userId)}&limit=10`,
    [userId]
  );

  const refresh = async () => {
    setLoading(true);
    try {
      const [s, c, r] = await Promise.all([
        fetch(`${API_BASE}/tools/web_rag/status?user_id=${encodeURIComponent(userId)}`, {
          cache: "no-store",
        }).then((x) => x.json()),
        fetch(chunksUrl, { cache: "no-store" }).then((x) => x.json()),
        fetch(rawUrl, { cache: "no-store" }).then((x) => x.json()),
      ]);
      const o = await fetch(
        `${API_BASE}/tools/overview?user_id=${encodeURIComponent(userId)}`,
        { cache: "no-store" }
      ).then((x) => x.json());
      setStatus(s);
      setChunks(Array.isArray(c?.items) ? c.items : []);
      setRaw(Array.isArray(r?.items) ? r.items : []);
      setOverview(o);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(id);
  }, [userId, chunksUrl, rawUrl]);

  const runTestSearch = async () => {
    const res = await fetch(`${API_BASE}/tools/web_rag/test-search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, query, k: 5 }),
    });
    setSearchResult(await res.json());
  };

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 text-sm">
      <header className="flex items-center justify-between border-b pb-3">
        <h1 className="text-lg font-semibold">Web RAG Admin</h1>
        <Link className="rounded border px-3 py-1" href="/">
          Back to chat
        </Link>
      </header>

      <section className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">User ID</span>
          <input
            className="rounded border px-2 py-1"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
          />
        </label>
        <button className="rounded border px-3 py-1" onClick={() => void refresh()}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
        <a
          className="rounded border px-3 py-1"
          href={`${API_BASE}/tools/web_rag/download/chunks?user_id=${encodeURIComponent(userId)}`}
          target="_blank"
          rel="noreferrer"
        >
          Download chunks
        </a>
        <a
          className="rounded border px-3 py-1"
          href={`${API_BASE}/tools/web_rag/download/raw?user_id=${encodeURIComponent(userId)}`}
          target="_blank"
          rel="noreferrer"
        >
          Download raw sources
        </a>
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
