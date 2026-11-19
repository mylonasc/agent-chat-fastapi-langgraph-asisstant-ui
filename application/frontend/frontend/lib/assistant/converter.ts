/**
 * Shared chat transport message conversion.
 *
 * Both UI presets feed the same backend transcript shapes into assistant-ui's
 * transport runtime. The full preset hydrates stored Assistant UI transcripts
 * verbatim and only surfaces optimistic user turns while a send is in flight;
 * the minimal preset keeps optimistic user turns until the server echoes them
 * back. Those differences are explicit policies here instead of duplicated
 * converter implementations.
 */
import {
  convertLangChainMessages,
  type LangChainMessage,
} from "@assistant-ui/react-langgraph";

import {
  createMessageConverter,
  type AssistantTransportCommand,
  type AssistantTransportConnectionMetadata,
  type ThreadMessage,
  type ThreadMessageLike,
} from "./runtime-compat";

const LangChainMessageConverter = createMessageConverter(
  convertLangChainMessages,
);

/**
 * Transport state messages are LangChain messages while a run is active, but
 * transcript hydration replaces them with complete Assistant UI rows.
 */
export type ChatTransportMessage = LangChainMessage | ThreadMessageLike;

export type ChatTransportState = {
  messages: readonly ChatTransportMessage[];
  thread_id?: string;
  user_id?: string;
};

export type OptimisticHumanPolicy =
  /** Only show the local turn while a request is in flight. */
  | "while-sending"
  /** Show the local turn until the backend transcript echoes it back. */
  | "until-echoed";

export type ChatMessageConverterOptions = {
  /** Prefix for synthetic IDs when a converted message has no usable ID. */
  syntheticIdPrefix: string;
  /** When not-yet-acknowledged user messages should appear in the thread. */
  optimisticHumans: OptimisticHumanPolicy;
  /**
   * Stored Assistant UI transcripts already contain rich parts (tool calls,
   * reasoning, sources). Re-converting them through the LangChain converter
   * would drop that structure.
   */
  hydrateStoredUiTranscript?: boolean;
};

export type ChatConverterResult = {
  messages: ThreadMessage[];
  isRunning: boolean;
};

export type ChatMessageConverter = (
  state: ChatTransportState | undefined,
  connectionMetadata: AssistantTransportConnectionMetadata,
) => ChatConverterResult;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * Stored transcripts are persisted in assistant-ui's own shape: `role` plus an
 * array of already-converted `content` parts. LangChain transport state uses a
 * discriminant `type` (`human`, `ai`, `tool`, `system`) instead.
 */
function isStoredUiTranscript(
  messages: readonly ChatTransportMessage[],
): boolean {
  return (
    messages.length > 0 &&
    messages.every((message) => {
      if (!("role" in message) || !("content" in message)) return false;
      const role = message.role;
      return (
        (role === "user" || role === "assistant") &&
        Array.isArray(message.content)
      );
    })
  );
}

function hasHumanMessage(messages: readonly ChatTransportMessage[]): boolean {
  return messages.some(
    (message) => "type" in message && message.type === "human",
  );
}

function addMessageCommands(
  commands: readonly AssistantTransportCommand[],
): Extract<AssistantTransportCommand, { type: "add-message" }>[] {
  return commands.filter(
    (
      command,
    ): command is Extract<AssistantTransportCommand, { type: "add-message" }> =>
      command.type === "add-message" && command.message.role === "user",
  );
}

function pendingHumanMessages(
  connectionMetadata: AssistantTransportConnectionMetadata,
): LangChainMessage[] {
  return addMessageCommands(connectionMetadata.pendingCommands).map(
    (command) => ({
      type: "human",
      content: command.message.parts
        .map((part) => (part.type === "text" ? part.text : ""))
        .join(""),
    }),
  );
}

function sourceMessageId(
  message: ChatTransportMessage | undefined,
): string | undefined {
  if (!isRecord(message)) return undefined;
  const id = message.id;
  return typeof id === "string" && id.length > 0 ? id : undefined;
}

/**
 * The LangChain converter is only ever handed LangChain-shaped transport
 * state. Stored UI transcripts are returned before this point; anything else
 * is the runtime state the backend emitted for the current run.
 */
function asLangChainMessages(
  messages: readonly ChatTransportMessage[],
): LangChainMessage[] {
  return messages as LangChainMessage[];
}

/**
 * Hydrated rows were produced by assistant-ui itself, so they already satisfy
 * the ThreadMessage contract even though the transport state type cannot say
 * so without losing the LangChain branch.
 */
function asThreadMessages(
  messages: readonly ChatTransportMessage[],
): ThreadMessage[] {
  return messages as unknown as ThreadMessage[];
}

export function createChatMessageConverter(
  options: ChatMessageConverterOptions,
): ChatMessageConverter {
  const hydrateStoredUiTranscript = options.hydrateStoredUiTranscript ?? false;

  return (state, connectionMetadata) => {
    const serverMessages = state?.messages ?? [];
    const isSending = connectionMetadata.isSending;

    if (
      hydrateStoredUiTranscript &&
      !isSending &&
      isStoredUiTranscript(serverMessages)
    ) {
      return { messages: asThreadMessages(serverMessages), isRunning: false };
    }

    const hasHumanInServer = hasHumanMessage(serverMessages);
    const includePendingHumans =
      options.optimisticHumans === "while-sending"
        ? isSending && !hasHumanInServer
        : !hasHumanInServer;

    const allMessages = includePendingHumans
      ? [...pendingHumanMessages(connectionMetadata), ...serverMessages]
      : serverMessages;

    const converted = LangChainMessageConverter.toThreadMessages(
      asLangChainMessages(allMessages),
    );

    // toThreadMessages may merge entries (for example tool-call round trips),
    // so converted[i] is not necessarily allMessages[i]. Only borrow a source
    // ID when cardinality is preserved 1:1; otherwise positional pairing would
    // attach IDs to the wrong messages and orphan feedback rows.
    const positional = converted.length === allMessages.length;
    const threadMessages = converted.map((message, index) => ({
      ...message,
      id:
        message.id ||
        (positional && sourceMessageId(allMessages[index])) ||
        `${options.syntheticIdPrefix}${index}`,
    }));

    return {
      // Stable logical IDs keep incremental repository updates in transcript
      // order, including across reloads and optimistic-message shifts.
      messages: threadMessages,
      isRunning: isSending,
    };
  };
}
