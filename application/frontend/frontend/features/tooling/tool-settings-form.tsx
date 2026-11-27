"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type {
  ToolSnapshot,
  ToolUpdate,
  ToolValue,
} from "@/lib/api/services/tooling";

export function ToolSettingsForm({
  snapshot,
  admin = false,
  readOnly = false,
  onSave,
}: {
  snapshot: ToolSnapshot;
  admin?: boolean;
  readOnly?: boolean;
  onSave: (body: ToolUpdate) => Promise<void>;
}) {
  const prefix = useId();
  const [draft, setDraft] = useState(() => structuredClone(snapshot));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const selectSet = (id: string, selected: boolean) => {
    setSaved(false);
    setDraft((state) => ({
      ...state,
      toolsets: selected
        ? [...state.toolsets, id]
        : state.toolsets.filter((name) => name !== id),
    }));
  };
  const change = (toolId: string, key: string, value: ToolValue) => {
    setSaved(false);
    setDraft((state) => ({
      ...state,
      catalog: state.catalog.map((group) => ({
        ...group,
        tools: group.tools.map((tool) =>
          tool.id !== toolId
            ? tool
            : key === "$enabled"
              ? { ...tool, selected: value as boolean }
              : { ...tool, config: { ...tool.config, [key]: value } },
        ),
      })),
    }));
  };
  const save = async () => {
    setBusy(true);
    setError(null);
    setSaved(false);
    const toolsets = draft.toolsets;
    const tools: ToolUpdate["tools"] = {};
    for (const group of draft.catalog) {
      if (!admin && !toolsets.includes(group.id)) continue;
      for (const tool of group.tools) {
        if (!admin && !tool.available) continue;
        tools[tool.id] = {
          enabled: tool.selected,
          config: Object.fromEntries(
            Object.entries(tool.config).filter(([key]) =>
              admin
                ? tool.fields[key]?.scope !== "startup"
                : tool.fields[key]?.scope === "conversation",
            ),
          ),
        };
      }
    }
    try {
      await onSave({
        revision: snapshot.revision,
        global_revision: snapshot.global_revision,
        toolsets,
        tools,
      });
      setSaved(true);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not save tool settings",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <form
      className="min-w-0 space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <p className="text-sm text-muted-foreground">
        {admin
          ? "Application policy limits what each conversation can use."
          : "Choose tools for this conversation. Administrator restrictions always apply."}{" "}
        Changes apply to the next turn, not a response already running.
      </p>
      <div className="grid min-w-0 gap-4 md:grid-cols-2">
        {draft.catalog.map((group) => {
          const selected = draft.toolsets.includes(group.id);
          const blocked = !admin && !group.available;
          return (
            <fieldset
              key={group.id}
              disabled={busy || readOnly || blocked}
              className="min-w-0 space-y-3 rounded-lg border p-4 [overflow-wrap:anywhere]"
            >
              <legend className="px-1 font-medium">{group.title}</legend>
              <label className="flex min-h-9 items-center gap-2">
                <input
                  type="checkbox"
                  checked={selected && !blocked}
                  onChange={(event) =>
                    selectSet(group.id, event.target.checked)
                  }
                />
                Enable {group.title} toolset
              </label>
              <p className="text-xs text-muted-foreground">
                {group.description}
              </p>
              {blocked && (
                <p className="text-xs text-muted-foreground">
                  Disabled by the administrator.
                </p>
              )}
              {group.tools.map((tool) => (
                <div key={tool.id} className="min-w-0 space-y-2 border-t pt-3">
                  <label className="flex min-h-9 items-center gap-2">
                    <input
                      type="checkbox"
                      checked={tool.selected}
                      disabled={!selected || (!admin && !tool.available)}
                      onChange={(event) =>
                        change(tool.id, "$enabled", event.target.checked)
                      }
                    />
                    Enable {tool.title}
                  </label>
                  <fieldset
                    disabled={!admin && (!selected || !tool.available)}
                    className="min-w-0 space-y-3"
                  >
                    <legend className="sr-only">
                      {tool.title} configuration
                    </legend>
                    {Object.entries(tool.fields).map(([key, field]) => {
                      const id = `${prefix}-${tool.id}-${key}`;
                      const locked =
                        field.scope === "startup" ||
                        (!admin && field.scope !== "conversation");
                      return (
                        <div key={key} className="min-w-0 space-y-1">
                          <label htmlFor={id} className="block text-sm">
                            {tool.title}: {field.label}
                          </label>
                          {field.type === "boolean" ? (
                            <input
                              id={id}
                              type="checkbox"
                              disabled={locked}
                              checked={Boolean(tool.config[key])}
                              onChange={(event) =>
                                change(tool.id, key, event.target.checked)
                              }
                            />
                          ) : field.type === "enum" ? (
                            <select
                              id={id}
                              disabled={locked}
                              value={String(tool.config[key])}
                              onChange={(event) =>
                                change(tool.id, key, event.target.value)
                              }
                              className="h-9 w-full min-w-0 rounded-md border bg-background px-2 text-sm"
                            >
                              {field.choices.map((choice) => (
                                <option key={choice}>{choice}</option>
                              ))}
                            </select>
                          ) : (
                            <Input
                              id={id}
                              type="number"
                              required
                              min={field.minimum ?? undefined}
                              max={field.maximum ?? undefined}
                              step={1}
                              disabled={locked}
                              value={Number(tool.config[key])}
                              onChange={(event) =>
                                change(tool.id, key, event.target.valueAsNumber)
                              }
                            />
                          )}
                          {locked && (
                            <p className="text-xs text-muted-foreground">
                              {field.scope === "startup"
                                ? "Startup-only; changing this requires reindexing and a restart."
                                : "Administrator-controlled setting."}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </fieldset>
                </div>
              ))}
            </fieldset>
          );
        })}
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error} Refresh settings before retrying if another window changed
          them.
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm">
          Tool settings saved.
        </p>
      )}
      {!readOnly && (
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save tool settings"}
        </Button>
      )}
    </form>
  );
}
