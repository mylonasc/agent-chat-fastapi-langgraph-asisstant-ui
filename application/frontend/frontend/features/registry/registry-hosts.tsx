"use client";

import Link from "next/link";
import type { FC } from "react";

import { Button } from "@/components/ui/button";
import { useApiClient } from "@/hooks/use-api-client";

import { HEADER_ACTION_REGISTRY } from "./header-action-registry";
import { STATUS_PANEL_REGISTRY } from "./status-panel-registry";
import { TOOL_UI_REGISTRY } from "./tool-ui-registry";

/** Mount the tool renderers enabled for this deployment. */
export const ToolUiHost: FC = () => {
  const { config } = useApiClient();
  return (
    <>
      {TOOL_UI_REGISTRY.filter((entry) => entry.isEnabled(config)).map(
        ({ id, Component }) => (
          <Component key={id} />
        ),
      )}
    </>
  );
};

/** Mount the transcript status panels enabled for this deployment. */
export const StatusPanelHost: FC = () => {
  const { config } = useApiClient();
  return (
    <>
      {STATUS_PANEL_REGISTRY.filter((entry) => entry.isEnabled(config)).map(
        ({ id, Component }) => (
          <Component key={id} />
        ),
      )}
    </>
  );
};

/** Render the header actions enabled for this deployment. */
export const HeaderActionHost: FC = () => {
  const { config } = useApiClient();
  const actions = HEADER_ACTION_REGISTRY.filter((entry) =>
    entry.isEnabled(config),
  );
  if (actions.length === 0) return null;
  return (
    <div className="flex items-center gap-2">
      {actions.map((action) => (
        <Button key={action.id} asChild variant="outline" size="sm">
          <Link href={action.href}>{action.label}</Link>
        </Button>
      ))}
    </div>
  );
};
