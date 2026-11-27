"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApiClient } from "@/hooks/use-api-client";
import type { ToolSnapshot } from "@/lib/api/services/tooling";
import { ToolSettingsForm } from "@/features/tooling/tool-settings-form";

export default function ToolsPage() {
  const { client, config, loaded } = useApiClient();
  const [snapshot, setSnapshot] = useState<ToolSnapshot | null>(null);
  const [token, setToken] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (!loaded || !config.tooling?.enabled) return;
    let active = true;
    client.tooling
      .catalog()
      .then((value) => {
        if (active) setSnapshot(value);
      })
      .catch((cause) => {
        if (active)
          setError(
            cause instanceof Error ? cause.message : "Could not load tools",
          );
      });
    return () => {
      active = false;
    };
  }, [client, loaded, config.tooling?.enabled]);
  const refresh = async (unlock = authorized) => {
    setError(null);
    try {
      setSnapshot(
        unlock
          ? await client.tooling.admin(token)
          : await client.tooling.catalog(),
      );
      setAuthorized(unlock);
    } catch (cause) {
      setAuthorized(false);
      setError(
        cause instanceof Error
          ? cause.message
          : "Administrator access required",
      );
    }
  };
  return (
    <main className="mx-auto min-h-dvh max-w-5xl space-y-5 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b pb-3">
        <h1 className="text-xl font-semibold">Toolsets and tools</h1>
        <Button asChild variant="outline">
          <Link href="/">Back to chat</Link>
        </Button>
      </header>
      {!loaded ? (
        <p role="status">Loading capabilities…</p>
      ) : !config.tooling?.enabled ? (
        <p>Tool management is not enabled by this deployment.</p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Available toolsets are baked into the deployment. Administrators can
            change application policy; conversations can only use a permitted
            subset.
          </p>
          <form
            className="flex flex-wrap items-end gap-3 rounded-lg border p-4"
            onSubmit={(event) => {
              event.preventDefault();
              void refresh(true);
            }}
          >
            <div className="min-w-0 flex-1 space-y-1">
              <label htmlFor="tool-admin-token" className="text-sm">
                Administrator token (or use your trusted admin session)
              </label>
              <Input
                id="tool-admin-token"
                type="password"
                autoComplete="off"
                value={token}
                onChange={(event) => {
                  setToken(event.target.value);
                  setAuthorized(false);
                }}
              />
            </div>
            <Button type="submit">Unlock administration</Button>
          </form>
          <p className="text-xs text-muted-foreground">
            For local administration set AGENT_CHAT_ADMIN_TOKEN on the backend.
            Credentials are kept only in this page’s memory, never saved in tool
            settings or browser storage.
          </p>
          <Button variant="outline" onClick={() => void refresh()}>
            Refresh settings
          </Button>
          {authorized && (
            <Button
              variant="ghost"
              onClick={() => {
                setToken("");
                setAuthorized(false);
              }}
            >
              Lock administration
            </Button>
          )}
          {!authorized && (
            <p className="text-sm">
              Read-only catalogue. Unlock administration to change
              application-wide settings.
            </p>
          )}
          {snapshot && Array.isArray(snapshot.catalog) && (
            <ToolSettingsForm
              key={`${snapshot.revision}-${authorized}`}
              snapshot={snapshot}
              admin
              readOnly={!authorized}
              onSave={async (body) => {
                setSnapshot(await client.tooling.saveAdmin(body, token));
                setSaved(true);
              }}
            />
          )}
          {saved && <p role="status">Application tool settings saved.</p>}
        </>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </main>
  );
}
