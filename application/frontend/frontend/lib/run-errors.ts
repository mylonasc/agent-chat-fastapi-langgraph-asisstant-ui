/**
 * Per-thread run-failure store.
 *
 * The assistant transport drops the in-flight user message when a run
 * fails, so a failed send leaves no message behind to host the error.
 * The runtime's onError callback records the failure here (keyed by the
 * bound backend thread id) and the thread reads it back with
 * useSyncExternalStore. Entries are cleared when a new run starts.
 */

export interface ThreadRunError {
  /** Transport error text, e.g. `Status 503: {...}` with the backend payload. */
  text: string;
  /** Truncated text of the user message that failed to send, if known. */
  userText: string | null;
}

const runErrors = new Map<string, ThreadRunError>();
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) {
    listener();
  }
}

export function subscribeRunErrors(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getRunError(threadKey: string): ThreadRunError | null {
  return runErrors.get(threadKey) ?? null;
}

export function setRunError(threadKey: string, error: ThreadRunError): void {
  runErrors.set(threadKey, error);
  notify();
}

export function clearRunError(threadKey: string): void {
  if (runErrors.delete(threadKey)) {
    notify();
  }
}

/** Best-effort text of the failed user turn from transport commands. */
export function failedUserText(commands: readonly unknown[]): string | null {
  for (const command of commands) {
    const message = (command as { message?: unknown })?.message as
      | { parts?: unknown }
      | undefined;
    const parts = Array.isArray(message?.parts) ? message.parts : [];
    const text = parts
      .filter(
        (part): part is { type: string; text: string } =>
          (part as { type?: unknown })?.type === "text" &&
          typeof (part as { text?: unknown })?.text === "string",
      )
      .map((part) => part.text)
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
    if (text) {
      return text.length > 200 ? `${text.slice(0, 200)}…` : text;
    }
  }
  return null;
}
