import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  Loader2Icon,
  XCircleIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function safeParseJson(input: unknown): unknown {
  if (typeof input !== "string") return input;
  try {
    return JSON.parse(input);
  } catch {
    return input;
  }
}

export const ToolFallback: ToolCallMessagePartComponent = ({
  toolName,
  argsText,
  result,
  status,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const parsedResult = useMemo(() => safeParseJson(result), [result]);

  const isRunning = result === undefined;
  const isCancelled =
    status?.type === "incomplete" && status.reason === "cancelled";
  const cancelledReason =
    isCancelled && status.error
      ? typeof status.error === "string"
        ? status.error
        : JSON.stringify(status.error)
      : null;

  const statusText = useMemo(() => {
    if (isCancelled) return "Cancelled";
    if (isRunning) return "Running";
    if (parsedResult && typeof parsedResult === "object") {
      const parsedStatus = (parsedResult as { status?: string }).status;
      if (parsedStatus) return parsedStatus;
    }
    return "Completed";
  }, [isCancelled, isRunning, parsedResult]);

  return (
    <div
      className={cn(
        "aui-tool-fallback-root mb-4 flex w-full flex-col gap-3 rounded-lg border py-3",
        isCancelled && "border-muted-foreground/30 bg-muted/30",
      )}
    >
      <div className="aui-tool-fallback-header flex items-center gap-2 px-4">
        {isCancelled ? (
          <XCircleIcon className="aui-tool-fallback-icon size-4 text-muted-foreground" />
        ) : isRunning ? (
          <Loader2Icon className="size-4 animate-spin" />
        ) : (
          <CheckIcon className="aui-tool-fallback-icon size-4" />
        )}
        <p
          className={cn(
            "aui-tool-fallback-title flex-grow",
            isCancelled && "text-muted-foreground line-through",
          )}
        >
          Tool: <b>{toolName}</b> ({statusText})
        </p>
        <Button onClick={() => setIsCollapsed(!isCollapsed)}>
          {isCollapsed ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </Button>
      </div>

      {!isCollapsed && (
        <div className="aui-tool-fallback-content flex flex-col gap-2 border-t pt-2">
          {cancelledReason && (
            <div className="aui-tool-fallback-cancelled-root px-4">
              <p className="aui-tool-fallback-cancelled-header mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Cancelled reason
              </p>
              <p className="aui-tool-fallback-cancelled-reason whitespace-pre-wrap text-xs text-muted-foreground">
                {cancelledReason}
              </p>
            </div>
          )}
          <div
            className={cn(
              "aui-tool-fallback-args-root px-4",
              isCancelled && "opacity-60",
            )}
          >
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Arguments
            </p>
            <pre className="aui-tool-fallback-args-value whitespace-pre-wrap text-xs">
              {argsText}
            </pre>
          </div>

          {!isCancelled && result !== undefined && (
            <div className="aui-tool-fallback-result-root border-t border-dashed px-4 pt-2">
              <p className="aui-tool-fallback-result-header mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Result
              </p>
              <pre className="aui-tool-fallback-result-content whitespace-pre-wrap text-xs">
                {typeof parsedResult === "string"
                  ? parsedResult
                  : JSON.stringify(parsedResult, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
