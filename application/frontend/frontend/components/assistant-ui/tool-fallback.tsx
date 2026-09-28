import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  Loader2Icon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";

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
}) => {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const parsedResult = useMemo(() => safeParseJson(result), [result]);

  const isRunning = result === undefined;

  const statusText = useMemo(() => {
    if (isRunning) return "Running";
    if (parsedResult && typeof parsedResult === "object") {
      const status = (parsedResult as { status?: string }).status;
      if (status) return status;
    }
    return "Completed";
  }, [isRunning, parsedResult]);

  return (
    <div className="aui-tool-fallback-root mb-4 flex w-full flex-col gap-3 rounded-lg border py-3">
      <div className="aui-tool-fallback-header flex items-center gap-2 px-4">
        {isRunning ? (
          <Loader2Icon className="size-4 animate-spin" />
        ) : (
          <CheckIcon className="aui-tool-fallback-icon size-4" />
        )}
        <p className="aui-tool-fallback-title flex-grow">
          Tool: <b>{toolName}</b> ({statusText})
        </p>
        <Button onClick={() => setIsCollapsed(!isCollapsed)}>
          {isCollapsed ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </Button>
      </div>

      {!isCollapsed && (
        <div className="aui-tool-fallback-content flex flex-col gap-2 border-t pt-2">
          <div className="aui-tool-fallback-args-root px-4">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Arguments
            </p>
            <pre className="aui-tool-fallback-args-value whitespace-pre-wrap text-xs">
              {argsText}
            </pre>
          </div>

          {result !== undefined && (
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
