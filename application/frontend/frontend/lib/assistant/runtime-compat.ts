/**
 * Single compatibility boundary for assistant-ui runtime APIs.
 *
 * assistant-ui marks the transport converter and remote thread-list runtime as
 * `unstable_*`. Keeping those imports here means application and presentation
 * code depend on stable local names and only this module needs updating when
 * the upstream signatures change.
 */
import {
  unstable_createMessageConverter,
  unstable_useRemoteThreadListRuntime,
} from "@assistant-ui/react";
import type {
  AssistantTransportCommand,
  AssistantTransportConnectionMetadata,
  ThreadMessage,
  ThreadMessageLike,
  unstable_RemoteThreadListAdapter as RemoteThreadListAdapter,
} from "@assistant-ui/react";

export const createMessageConverter = unstable_createMessageConverter;
export const useRemoteThreadListRuntime = unstable_useRemoteThreadListRuntime;

/** The metadata shape the remote thread-list adapter returns per thread. */
export type RemoteThreadMetadata = Awaited<
  ReturnType<RemoteThreadListAdapter["fetch"]>
>;

export type {
  AssistantTransportCommand,
  AssistantTransportConnectionMetadata,
  RemoteThreadListAdapter,
  ThreadMessage,
  ThreadMessageLike,
};

type ExternalThreadState = {
  thread_id?: string;
  messages: readonly unknown[];
};

/**
 * Load a stored transcript into an already-mounted thread runtime.
 *
 * `unstable_loadExternalState` is an unstable method on the thread runtime.
 * Returns `false` when the runtime does not expose it so callers can skip the
 * hydration path instead of casting the runtime to `any`.
 */
export function loadExternalThreadState(
  runtime: unknown,
  state: ExternalThreadState,
): boolean {
  if (!runtime || typeof runtime !== "object") return false;
  const thread = (runtime as { thread?: unknown }).thread;
  if (!thread || typeof thread !== "object") return false;
  const loader = (thread as { unstable_loadExternalState?: unknown })
    .unstable_loadExternalState;
  if (typeof loader !== "function") return false;
  Reflect.apply(loader, thread, [state]);
  return true;
}
