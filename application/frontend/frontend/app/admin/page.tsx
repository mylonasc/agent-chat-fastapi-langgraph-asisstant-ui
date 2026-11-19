"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  AdminJobs,
  AdminOverview,
  AdminSourcePreviews,
  AdminTestSearch,
} from "@/features/admin/admin-sections";
import { useAdminRag } from "@/features/admin/use-admin-rag";

export default function AdminPage() {
  const admin = useAdminRag();

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 text-sm">
      <header className="flex items-center justify-between border-b pb-3">
        <h1 className="text-lg font-semibold">Web RAG Admin</h1>
        <Button asChild variant="outline" size="sm">
          <Link href="/">Back to chat</Link>
        </Button>
      </header>

      {!admin.loaded && (
        <p role="status" className="rounded border p-3 text-xs text-muted-foreground">
          Loading administration capabilities…
        </p>
      )}
      {admin.loaded && !admin.adminEnabled && (
        <section className="rounded border border-dashed p-3 text-xs text-muted-foreground">
          The admin capability is disabled on this backend (see <code>/api/config</code>).
          This page performs no requests.
        </section>
      )}
      {admin.loaded && admin.adminEnabled && !admin.ragEnabled && (
        <section className="rounded border border-dashed p-3 text-xs text-muted-foreground">
          The Web RAG capability is disabled on this backend (see <code>/api/config</code>).
          Point this UI at the full backend to manage the index.
        </section>
      )}

      {admin.error && (
        <section
          role="alert"
          className="flex items-center justify-between gap-3 rounded border border-destructive bg-destructive/10 p-3 text-xs text-destructive"
        >
          <span>{admin.error}</span>
          <Button variant="outline" size="sm" onClick={() => void admin.refresh()}>
            Retry
          </Button>
        </section>
      )}

      <div>
        <Button disabled={!admin.ready || admin.loading} onClick={() => void admin.refresh()}>
          {admin.loading ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      <AdminOverview overview={admin.overview} />
      <AdminJobs status={admin.status} />
      <AdminSourcePreviews raw={admin.raw} chunks={admin.chunks} />
      <AdminTestSearch enabled={admin.ready} />
    </main>
  );
}
