import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  Loader2Icon,
  XCircleIcon,
} from "lucide-react";
import { useId, useMemo, useState, type FC } from "react";

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

export const ToolFallback: FC<
  ToolCallMessagePartProps & { initiallyExpanded?: boolean }
> = ({ toolName, argsText, result, status, initiallyExpanded = false }) => {
  const [isCollapsed, setIsCollapsed] = useState(!initiallyExpanded);
  const contentId = useId();
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
      <div className="aui-tool-fallback-header flex min-w-0 items-center gap-2 px-4">
        {isCancelled ? (
          <XCircleIcon className="aui-tool-fallback-icon size-4 text-muted-foreground" />
        ) : isRunning ? (
          <Loader2Icon className="size-4 animate-spin" />
        ) : (
          <CheckIcon className="aui-tool-fallback-icon size-4" />
        )}
        <p
          className={cn(
            "aui-tool-fallback-title min-w-0 flex-grow [overflow-wrap:anywhere]",
            isCancelled && "text-muted-foreground line-through",
          )}
        >
          Tool: <b>{toolName}</b> ({statusText})
        </p>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="shrink-0"
          aria-label={`${isCollapsed ? "Expand" : "Collapse"} ${toolName} details`}
          aria-expanded={!isCollapsed}
          aria-controls={!isCollapsed ? contentId : undefined}
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isCollapsed ? <ChevronDownIcon /> : <ChevronUpIcon />}
        </Button>
      </div>

      {!isCollapsed && (
        <div
          id={contentId}
          className="aui-tool-fallback-content flex min-w-0 flex-col gap-2 border-t pt-2 [overflow-wrap:anywhere]"
        >
          {cancelledReason && (
            <div className="aui-tool-fallback-cancelled-root px-4">
              <p className="aui-tool-fallback-cancelled-header mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                Cancelled reason
              </p>
              <p className="aui-tool-fallback-cancelled-reason text-xs whitespace-pre-wrap text-muted-foreground">
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
            <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Arguments
            </p>
            <pre className="aui-tool-fallback-args-value text-xs whitespace-pre-wrap">
              {argsText}
            </pre>
          </div>

          {!isCancelled && result !== undefined && (
            <div className="aui-tool-fallback-result-root border-t border-dashed px-4 pt-2">
              <p className="aui-tool-fallback-result-header mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                Result
              </p>
              <pre className="aui-tool-fallback-result-content text-xs whitespace-pre-wrap">
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
