"use client";

import {
  ErrorPrimitive,
  MessagePrimitive,
  useAssistantState,
} from "@assistant-ui/react";
import { useEffect, useRef, useSyncExternalStore, type FC } from "react";

import { useApiClient } from "@/hooks/use-api-client";
import {
  clearRunError,
  getRunError,
  subscribeRunErrors,
} from "@/lib/run-errors";

/**
 * Split a transport failure into a short title and backend detail. The
 * transport throws `Status <code>: <body>` where the body is the JSON
 * error payload the backend served (error/message/hint); mid-stream
 * provider failures arrive as the same JSON without the Status prefix.
 */
function parseErrorPayload(body: string): {
  code: string | null;
  detail: string;
} | null {
  try {
    const payload = JSON.parse(body);
    const detailObj = payload?.detail ?? payload;
    const code = typeof detailObj?.error === "string" ? detailObj.error : null;
    const message =
      typeof detailObj?.message === "string" ? detailObj.message : null;
    const hint = typeof detailObj?.hint === "string" ? detailObj.hint : null;
    const detail = [message, hint].filter(Boolean).join("\n") || body;
    return { code, detail };
  } catch {
    return null;
  }
}

function formatBackendError(raw: unknown): {
  title: string;
  detail: string | null;
} {
  const text = raw instanceof Error ? raw.message : String(raw ?? "");
  const match = text.match(/^Status (\d+):\s*([\s\S]*)$/);
  if (!match) {
    const parsed = parseErrorPayload(text);
    if (!parsed) return { title: "Assistant error", detail: text || null };
    return {
      title: `Assistant error${parsed.code ? ` · ${parsed.code}` : ""}`,
      detail: parsed.detail,
    };
  }
  const [, status, body] = match;
  const parsed = parseErrorPayload(body);
  if (!parsed)
    return { title: `Request failed (${status})`, detail: body || null };
  return {
    title: `Request failed (${status})${parsed.code ? ` · ${parsed.code}` : ""}`,
    detail: parsed.detail,
  };
}

const RunErrorBody: FC<{ error: unknown; debug: boolean }> = ({
  error,
  debug,
}) => {
  if (!debug) {
    return (
      <span className="aui-message-error-generic">
        The assistant is unavailable right now. Please try again later.
      </span>
    );
  }
  const { title, detail } = formatBackendError(error);
  return (
    <span className="aui-message-error-debug flex flex-col gap-1">
      <span className="aui-message-error-title font-medium">{title}</span>
      {detail && (
        <pre className="aui-message-error-detail overflow-x-auto rounded bg-background/60 p-2 font-mono text-xs whitespace-pre-wrap">
          {detail}
        </pre>
      )}
    </span>
  );
};

/** Error attached to the assistant message itself, if the runtime emits one. */
export const MessageError: FC = () => {
  const { config } = useApiClient();
  const debug = config.server_mode === "debug";
  const messageError = useAssistantState((state) => {
    const status = (state.message as unknown as { status?: unknown })
      ?.status as { error?: unknown } | undefined;
    return status?.error;
  });
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive dark:bg-destructive/5 dark:text-red-200">
        <div className="aui-message-error-message">
          <RunErrorBody error={messageError} debug={debug} />
        </div>
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
};

/**
 * A failed run drops the in-flight user message, so no message is left to
 * host the error. The transport records failures per thread (see
 * lib/run-errors); surface the latest one thread-wide with the same
 * debug/prod policy as message errors. A new run clears it.
 */
export const ThreadRunError: FC = () => {
  const { config } = useApiClient();
  const debug = config.server_mode === "debug";
  const threadItem = useAssistantState((state) => state.threadListItem);
  const isRunning = useAssistantState((state) => state.thread.isRunning);
  const threadKey = threadItem?.remoteId ?? threadItem?.id ?? "";
  const failure = useSyncExternalStore(subscribeRunErrors, () =>
    threadKey ? getRunError(threadKey) : null,
  );
  const wasRunning = useRef(isRunning);
  useEffect(() => {
    if (isRunning && !wasRunning.current && threadKey) {
      clearRunError(threadKey);
    }
    wasRunning.current = isRunning;
  }, [isRunning, threadKey]);
  if (!failure || isRunning) return null;
  return (
    <div className="aui-thread-error mx-auto w-full max-w-[var(--thread-max-width)] px-2 pb-2">
      <div
        role="alert"
        className="aui-thread-error-root rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive dark:bg-destructive/5 dark:text-red-200"
      >
        {failure.userText && (
          <p className="aui-thread-error-usertext mb-1 font-medium">
            Could not send: “{failure.userText}”
          </p>
        )}
        <RunErrorBody error={failure.text} debug={debug} />
      </div>
    </div>
  );
};
