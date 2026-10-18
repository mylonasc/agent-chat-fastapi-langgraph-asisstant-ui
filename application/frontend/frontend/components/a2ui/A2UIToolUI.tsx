"use client";

import { useAssistantApi, makeAssistantToolUI } from "@assistant-ui/react";
import type { A2UIAction } from "@a2ui-sdk/react/0.9";
import { A2UISurface, isA2UIResult } from "./A2UISurface";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";

function useActionForwarder() {
  const api = useAssistantApi();
  return (action: A2UIAction) => {
    // Resilient default: turn the declarative action into ordinary chat
    // text over the existing transport. No dedicated endpoint needed.
    const name =
      (action as { name?: unknown }).name ??
      (action as { action?: { name?: unknown } }).action?.name ??
      "a2ui_action";
    const text = `[a2ui-action ${String(name)}] ${JSON.stringify(action)}`;
    try {
      const thread = (api as unknown as { thread?: () => unknown }).thread?.();
      const append = (thread as { append?: unknown })?.append;
      if (typeof append === "function") {
        void (append as (msg: unknown) => Promise<unknown>).call(thread, {
          role: "user",
          content: [{ type: "text", text }],
        });
        return;
      }
      const composer = (api as unknown as { composer?: () => unknown }).composer?.();
      const sendWithText = (composer as { sendWithText?: unknown })?.sendWithText;
      if (typeof sendWithText === "function") {
        void (sendWithText as (t: string) => unknown).call(composer, text);
      }
    } catch {
      // Action display still rendered; send failure must not break the UI.
    }
  };
}

function makeA2UIToolUI(toolName: string) {
  return makeAssistantToolUI({
    toolName,
    render: ({ result, status, ...rest }) => {
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
