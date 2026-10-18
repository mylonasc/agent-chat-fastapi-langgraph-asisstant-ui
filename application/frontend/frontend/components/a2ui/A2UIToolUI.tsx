"use client";

import {
  useAssistantApi,
  useAssistantState,
  makeAssistantToolUI,
} from "@assistant-ui/react";
import type { A2UIAction } from "@a2ui-sdk/react/0.9";
import { A2UISurface, isA2UIResult } from "./A2UISurface";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { useApiClient } from "@/hooks/use-api-client";

function actionName(action: A2UIAction): string {
  const name =
    (action as { name?: unknown }).name ??
    (action as { action?: { name?: unknown } }).action?.name;
  return typeof name === "string" && name ? name : "a2ui_action";
}

function appendLocal(
  api: ReturnType<typeof useAssistantApi>,
  message: { id?: string; role: "user"; content: { type: "text"; text: string }[] },
) {
  try {
    const thread = (api as unknown as { thread?: () => unknown }).thread?.();
    const append = (thread as { append?: unknown })?.append;
    if (typeof append === "function") {
      void (append as (msg: unknown) => Promise<unknown>).call(thread, message);
      return;
    }
    const text = message.content.map((p) => p.text).join("");
    const composer = (api as unknown as { composer?: () => unknown }).composer?.();
    const sendWithText = (composer as { sendWithText?: unknown })?.sendWithText;
    if (typeof sendWithText === "function") {
      void (sendWithText as (t: string) => unknown).call(composer, text);
    }
  } catch {
    // Action display still rendered; send failure must not break the UI.
  }
}

function useActionForwarder() {
  const api = useAssistantApi();
  const { client, loaded } = useApiClient();
  const threadItem = useAssistantState((s) => s.threadListItem);
  return (action: A2UIAction) => {
    const name = actionName(action);
    const context =
      action && typeof action === "object" && "context" in action &&
      action.context && typeof action.context === "object"
        ? (action.context as Record<string, unknown>)
        : {};
    // Legacy byte-compatible text; also the no-endpoint fallback.
    const legacyText = `[a2ui-action ${name}] ${JSON.stringify(action)}`;
    const threadId = threadItem.remoteId;
    if (!loaded || !threadId) {
      appendLocal(api, { role: "user", content: [{ type: "text", text: legacyText }] });
      return;
    }
    const actionId =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `act-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
    void (async () => {
      try {
        const stored = await client.postA2UIAction(threadId, {
          surface_id: String(action.surfaceId ?? "unknown"),
          component_id: String(action.sourceComponentId ?? "unknown"),
          action: { name, context },
          action_id: actionId,
        });
        appendLocal(api, {
          id: stored.message_id,
          role: "user",
          content: [{ type: "text", text: stored.text }],
        });
      } catch {
        // Old server (404) or offline: identical UX via local append; the
        // debounced transcript synchronizer persists it like any message.
        appendLocal(api, {
          id: actionId,
          role: "user",
          content: [{ type: "text", text: legacyText }],
        });
      }
    })();
  };
}

function makeA2UIToolUI(toolName: string) {
  return makeAssistantToolUI({
    toolName,
    render: ({ result, status, toolName: _ignored, ...rest }) => {
      const forward = useActionForwarder();
      if (status.type === "running" && result === undefined) {
        return (
          <div className="mb-3 rounded-xl border px-3 py-2 text-xs text-muted-foreground">
            {toolName} is rendering…
          </div>
        );
      }
      if (!isA2UIResult(result)) {
        // Not an a2ui envelope (or malformed): keep the generic fallback
        // so unknown tools never white-screen.
        const Fallback = ToolFallback as unknown as React.FC<Record<string, unknown>>;
        return <Fallback result={result} status={status} toolName={toolName} {...rest} />;
      }
      return <A2UISurface result={result} onAction={forward} />;
    },
  });
}

// One isolated surface per tool call: each envelope carries its own
// createSurface messages, so concurrent calls never share state.
export const RenderA2UIDemoToolUI = makeA2UIToolUI("render_a2ui_demo");
export const RenderNetworkA2UIToolUI = makeA2UIToolUI("render_network_a2ui");
