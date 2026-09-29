"use client";

import { ShareButton } from "./share-button";
import Link from "next/link";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CopyIcon,
  PencilIcon,
  RefreshCwIcon,
  Square,
  ThumbsDownIcon,
  ThumbsUpIcon,
} from "lucide-react";

import {
  ActionBarPrimitive,
  BranchPickerPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAssistantApi,
  useAssistantState,
} from "@assistant-ui/react";

import type { FC } from "react";
import { useEffect, useRef, useState } from "react";
import { LazyMotion, MotionConfig, domAnimation } from "motion/react";
import * as m from "motion/react-m";

import { Button } from "@/components/ui/button";
import { useApiClient } from "@/hooks/use-api-client";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { Reasoning, ReasoningGroup } from "@/components/assistant-ui/reasoning";
import {
  WebRAGStatusToolUI,
  WebRAGToolUI,
  WebSearchToolUI,
} from "@/components/assistant-ui/source-indexing-widget";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import {
  ComposerAddAttachment,
  ComposerAttachments,
  UserMessageAttachments,
} from "@/components/assistant-ui/attachment";

import { cn } from "@/lib/utils";

export const Thread: FC = () => {
  const { config } = useApiClient();
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <ThreadPrimitive.Root
          className="aui-root aui-thread-root @container flex h-full flex-col bg-background"
          style={{
            ["--thread-max-width" as string]: "44rem",
          }}
        >
          <div className="flex items-center justify-between border-b px-4 py-2">
            <ChatTitle />
            <div className="flex items-center gap-2">
              {config.tools.admin.enabled && (
                <Button asChild variant="outline" size="sm">
                  <Link href="/admin">Admin</Link>
                </Button>
              )}
              {config.tools.sharing.enabled && <ShareButton />}
            </div>
          </div>

          <WebSearchToolUI />
           <WebRAGToolUI />
           <WebRAGStatusToolUI />
           <AutoThreadTitle />
           <RememberRemoteThread />
           <TranscriptSynchronizer />

          <ThreadPrimitive.Viewport className="aui-thread-viewport relative flex flex-1 flex-col overflow-x-auto overflow-y-scroll px-4">
            <ThreadPrimitive.If empty>
              <ThreadWelcome />
            </ThreadPrimitive.If>

            <ThreadPrimitive.Messages
              components={{
                UserMessage,
                EditComposer,
                AssistantMessage,
              }}
            />

            <IndexingStatusPanel />

            <ThreadPrimitive.If empty={false}>
              <div className="aui-thread-viewport-spacer min-h-8 grow" />
            </ThreadPrimitive.If>

            <Composer />
          </ThreadPrimitive.Viewport>
        </ThreadPrimitive.Root>
      </MotionConfig>
    </LazyMotion>
  );
};

const ChatTitle: FC = () => {
  const api = useAssistantApi();
  const title = useAssistantState((s) => s.threadListItem.title ?? "New Chat");

  const rename = () => {
    const next = window.prompt("Rename chat", title);
    if (next == null) return;
    const cleaned = cleanTitle(next);
    if (!cleaned || cleaned === title) return;
    api.threadListItem().rename(cleaned);
  };

  return (
    <button
      type="button"
      onClick={rename}
      className="text-sm font-medium hover:underline"
      title="Rename chat"
    >
      {title}
    </button>
  );
};

const AUTO_TITLE_DEFAULTS = new Set(["", "New Chat", "Untitled"]);

function cleanTitle(input: string): string {
  const compact = input.replace(/\s+/g, " ").trim();
  const stripped = compact.replace(/^[-:.,\s]+|[-:.,\s]+$/g, "");
  return stripped.slice(0, 64);
}

function deriveThreadTitle(messages: readonly any[]): string | null {
  const userMessages = messages.filter((m) => m?.role === "user");
  const assistantMessages = messages.filter((m) => m?.role === "assistant");

  if (userMessages.length < 2 || assistantMessages.length < 2) {
    return null;
  }

  const userText = userMessages
    .flatMap((m) => (Array.isArray(m?.content) ? m.content : []))
    .filter((p) => p?.type === "text")
    .map((p) => String(p?.text ?? ""))
    .join(" ");

  const cleaned = cleanTitle(userText);
  if (!cleaned) return null;

  return cleaned;
}

const AutoThreadTitle: FC = () => {
  const api = useAssistantApi();
  const threadItem = useAssistantState((s) => s.threadListItem);
  const messages = useAssistantState((s) => s.thread.messages);
  const autoTitledByThreadRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const threadId = threadItem.remoteId ?? threadItem.id;
    const currentTitle = String(threadItem.title ?? "");

    if (!threadId) return;
    if (!AUTO_TITLE_DEFAULTS.has(currentTitle)) return;
    if (autoTitledByThreadRef.current.has(threadId)) return;

    const suggested = deriveThreadTitle(messages as readonly any[]);
    if (!suggested || AUTO_TITLE_DEFAULTS.has(suggested)) return;

    autoTitledByThreadRef.current.add(threadId);
    api.threadListItem().rename(suggested);
  }, [api, messages, threadItem.id, threadItem.remoteId, threadItem.title]);

  return null;
};

const ACTIVE_THREAD_STORAGE_KEY = "agent-chat.active-thread.v1";

/** Restore the user's selected owned thread rather than a fresh local draft. */
const RememberRemoteThread: FC = () => {
  const api = useAssistantApi();
  const threadItem = useAssistantState((s) => s.threadListItem);
  const isLoading = useAssistantState((s) => s.threads.isLoading);
  const threadItems = useAssistantState((s) => s.threads.threadItems);
  const restoredInitialThread = useRef(false);

  useEffect(() => {
    if (threadItem.remoteId) {
      localStorage.setItem(ACTIVE_THREAD_STORAGE_KEY, threadItem.remoteId);
      return;
    }
    if (isLoading || restoredInitialThread.current) return;
    const saved = localStorage.getItem(ACTIVE_THREAD_STORAGE_KEY);
    if (!saved) {
      restoredInitialThread.current = true;
      return;
    }
    if (!threadItems.some((item) => item.remoteId === saved)) return;
    restoredInitialThread.current = true;
    api.threads().switchToThread(saved);
  }, [api, isLoading, threadItems, threadItem.remoteId]);

  return null;
};

/** Persist only completed turns; stable message IDs make retries idempotent. */
const TranscriptSynchronizer: FC = () => {
  const { client } = useApiClient();
  const threadItem = useAssistantState((s) => s.threadListItem);
  const messages = useAssistantState((s) => s.thread.messages);
  const isRunning = useAssistantState((s) => s.thread.isRunning);
  const syncedPayloads = useRef(new Map<string, string>());

  useEffect(() => {
    const threadId = threadItem.remoteId;
    if (!threadId || messages.length === 0) return;
    // Transport removes pending user commands after a completed run. Store
    // user messages while they are still present; assistant payloads remain
    // deferred until their final immutable state is available.
    const messagesToSync = isRunning
      ? messages.filter((message) => message.role === "user")
      : messages;
    if (messagesToSync.length === 0) return;

    // Assistant UI can publish a final state immediately after isRunning flips.
    // Wait for that burst to settle before storing an immutable transcript row.
    const timer = window.setTimeout(() => {
      void (async () => {
        for (const message of messagesToSync) {
          if (message.id == null) continue;
          const payload = JSON.stringify(message);
          if (syncedPayloads.current.get(message.id) === payload) continue;
          await client.appendMessage(threadId, message);
          syncedPayloads.current.set(message.id, payload);
        }
      })().catch(() => {
        // The next completed turn retries unchanged message IDs without duplicates.
      });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [client, isRunning, messages, threadItem.id, threadItem.remoteId]);

  return null;
};

const ThreadScrollToBottom: FC = () => {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <TooltipIconButton
        tooltip="Scroll to bottom"
        variant="outline"
        className="aui-thread-scroll-to-bottom absolute -top-12 z-10 self-center rounded-full p-4 disabled:invisible dark:bg-background dark:hover:bg-accent"
      >
        <ArrowDownIcon />
      </TooltipIconButton>
    </ThreadPrimitive.ScrollToBottom>
  );
};

/**
 * Ensure the current thread is initialized before allowing any send.
 * This prevents POST /assistant with thread_id="new".
 */
function useEnsureThreadInitialized() {
  return { canSend: true, isInitializing: false };
}

const ThreadWelcome: FC = () => {
  const { canSend, isInitializing } = useEnsureThreadInitialized();

  return (
    <div className="aui-thread-welcome-root mx-auto my-auto flex w-full max-w-[var(--thread-max-width)] flex-grow flex-col">
      <div className="aui-thread-welcome-center flex w-full flex-grow flex-col items-center justify-center">
        <div className="aui-thread-welcome-message flex size-full flex-col justify-center px-8">
          <m.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="aui-thread-welcome-message-motion-1 text-2xl font-semibold"
          >
            Hello there!
          </m.h1>
          <m.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ delay: 0.1 }}
            className="aui-thread-welcome-message-motion-2 text-2xl text-muted-foreground/65"
          >
            How can I help you today?
          </m.div>

          {!canSend && (
            <div className="mt-4 text-sm text-muted-foreground">
              {isInitializing ? "Initializing chat…" : "Preparing chat…"}
            </div>
          )}
        </div>
      </div>

      {/* We’ll disable suggestion send until init completes */}
      <ThreadSuggestions disabled={!canSend} />
    </div>
  );
};

const ThreadSuggestions: FC<{ disabled?: boolean }> = ({ disabled }) => {
  return (
    <div className="aui-thread-welcome-suggestions grid w-full gap-2 pb-4 @md:grid-cols-2">
      {[
        {
          title: "Explain React hooks",
          label: "like useState and useEffect",
          action: "Explain React hooks like useState and useEffect",
        },
        {
          title: "Write a SQL query",
          label: "to find top customers",
          action: "Write a SQL query to find top customers",
        },
        {
          title: "Create a meal plan",
          label: "for healthy weight loss",
          action: "Create a meal plan for healthy weight loss",
        },
      ].map((suggestedAction, index) => (
        <m.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ delay: 0.05 * index }}
          key={`suggested-action-${suggestedAction.title}-${index}`}
          className="aui-thread-welcome-suggestion-display [&:nth-child(n+3)]:hidden @md:[&:nth-child(n+3)]:block"
        >
          <ThreadPrimitive.Suggestion
            prompt={suggestedAction.action}
            send={!disabled}
            asChild
          >
            <Button
              variant="ghost"
              disabled={disabled}
              className="aui-thread-welcome-suggestion h-auto w-full flex-1 flex-wrap items-start justify-start gap-1 rounded-3xl border px-5 py-4 text-left text-sm @md:flex-col dark:hover:bg-accent/60"
              aria-label={suggestedAction.action}
            >
              <span className="aui-thread-welcome-suggestion-text-1 font-medium">
                {suggestedAction.title}
              </span>
              <span className="aui-thread-welcome-suggestion-text-2 text-muted-foreground">
                {suggestedAction.label}
              </span>
            </Button>
          </ThreadPrimitive.Suggestion>
        </m.div>
      ))}
    </div>
  );
};

const Composer: FC = () => {
  const { canSend, isInitializing } = useEnsureThreadInitialized();
  const { config } = useApiClient();
  const attachmentsEnabled = config.tools.attachments.enabled;
  const contents = (
    <>
      {attachmentsEnabled && <ComposerAttachments />}
      <ComposerPrimitive.Input
        placeholder={canSend ? "Send a message..." : (isInitializing ? "Initializing chat..." : "Preparing chat...")}
        className="aui-composer-input mb-1 max-h-32 min-h-16 w-full resize-none bg-transparent px-3.5 pt-1.5 pb-3 text-base outline-none placeholder:text-muted-foreground focus-visible:ring-0"
        rows={1}
        autoFocus
        aria-label="Message input"
      />
      <ComposerAction canSend={canSend} attachmentsEnabled={attachmentsEnabled} />
    </>
  );

  return (
    <div className="aui-composer-wrapper sticky bottom-0 mx-auto flex w-full max-w-[var(--thread-max-width)] flex-col gap-4 overflow-visible rounded-t-3xl bg-background pb-4 md:pb-6">
      <ThreadScrollToBottom />

      <ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
        {attachmentsEnabled ? (
          <ComposerPrimitive.AttachmentDropzone className="aui-composer-attachment-dropzone group/input-group flex w-full flex-col rounded-3xl border border-input bg-background px-1 pt-2 shadow-xs transition-[color,box-shadow] outline-none has-[textarea:focus-visible]:border-ring has-[textarea:focus-visible]:ring-[3px] has-[textarea:focus-visible]:ring-ring/50 data-[dragging=true]:border-dashed data-[dragging=true]:border-ring data-[dragging=true]:bg-accent/50 dark:bg-background">
            {contents}
          </ComposerPrimitive.AttachmentDropzone>
        ) : (
          <div className="flex w-full flex-col rounded-3xl border border-input bg-background px-1 pt-2 shadow-xs dark:bg-background">
            {contents}
          </div>
        )}
      </ComposerPrimitive.Root>
    </div>
  );
};

const ComposerAction: FC<{ canSend: boolean; attachmentsEnabled: boolean }> = ({ canSend, attachmentsEnabled }) => {
  return (
    <div className="aui-composer-action-wrapper relative mx-1 mt-2 mb-2 flex items-center justify-between">
      {attachmentsEnabled && <ComposerAddAttachment />}

      <ThreadPrimitive.If running={false}>
        <ComposerPrimitive.Send asChild>
          <TooltipIconButton
            tooltip={canSend ? "Send message" : "Initializing…"}
            side="bottom"
            type="submit"
            variant="default"
            size="icon"
            disabled={!canSend}
            className="aui-composer-send size-[34px] rounded-full p-1"
            aria-label="Send message"
          >
            <ArrowUpIcon className="aui-composer-send-icon size-5" />
          </TooltipIconButton>
        </ComposerPrimitive.Send>
      </ThreadPrimitive.If>

      <ThreadPrimitive.If running>
        <ComposerPrimitive.Cancel asChild>
          <Button
            type="button"
            variant="default"
            size="icon"
            className="aui-composer-cancel size-[34px] rounded-full border border-muted-foreground/60 hover:bg-primary/75 dark:border-muted-foreground/90"
            aria-label="Stop generating"
          >
            <Square className="aui-composer-cancel-icon size-3.5 fill-white dark:fill-black" />
          </Button>
        </ComposerPrimitive.Cancel>
      </ThreadPrimitive.If>
    </div>
  );
};

const MessageError: FC = () => {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive dark:bg-destructive/5 dark:text-red-200">
        <ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
};

type IndexJob = {
  job_id: string;
  status: string;
  total_urls: number;
  completed_urls: number;
  failed_urls: number;
};

const IndexingStatusPanel: FC = () => {
  const [jobs, setJobs] = useState<IndexJob[]>([]);
  const { config, client } = useApiClient();
  const rag = config.tools.web_rag;
  const statusPath = rag.status_path ?? "/tools/web_rag/status";

  useEffect(() => {
    // Capability-gated: no polling when the backend does not serve RAG.
    if (!rag.enabled) {
      setJobs([]);
      return;
    }
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const data = await client.request<{ jobs?: IndexJob[] }>(statusPath);
        if (cancelled) return;

        const list = Array.isArray(data?.jobs) ? (data.jobs as IndexJob[]) : [];
        const active = list.filter((j) =>
          ["queued", "running"].includes((j?.status ?? "").toLowerCase())
        );
        setJobs(active);
      } catch {
        if (!cancelled) setJobs([]);
      }
    };

    void fetchStatus();
    const id = window.setInterval(fetchStatus, 1200);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [rag.enabled, statusPath, client]);

  if (!jobs.length) return null;

  return (
    <div className="mx-auto mt-2 w-full max-w-[var(--thread-max-width)] px-2">
      <div className="rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
        {jobs.map((job) => (
          <div key={job.job_id} className="mb-1 last:mb-0">
            Indexing {job.completed_urls}/{job.total_urls}
            {job.failed_urls ? ` (${job.failed_urls} failed)` : ""} - {job.status}
          </div>
        ))}
      </div>
    </div>
  );
};

const AssistantMessage: FC = () => {
  const messageId = useAssistantState((s) => s.message.id);
  return (
    <MessagePrimitive.Root asChild>
      <div
        className="aui-assistant-message-root relative mx-auto w-full max-w-[var(--thread-max-width)] animate-in py-4 duration-150 ease-out fade-in slide-in-from-bottom-1 last:mb-24"
        data-role="assistant"
        data-message-id={messageId}
      >
        <div className="aui-assistant-message-content mx-2 leading-7 break-words text-foreground">
          <MessagePrimitive.Parts
            components={{
              Text: MarkdownText,
              Reasoning: Reasoning,
              ReasoningGroup: ReasoningGroup,
              tools: { Fallback: ToolFallback },
            }}
          />
          <MessageError />
        </div>

        <div className="aui-assistant-message-footer mt-2 ml-2 flex">
          <BranchPicker />
          <AssistantActionBar />
          <MessageFeedbackControls />
        </div>
      </div>
    </MessagePrimitive.Root>
  );
};

const MessageFeedbackControls: FC = () => {
  const { client, identity } = useApiClient();
  const threadItem = useAssistantState((s) => s.threadListItem);
  const message = useAssistantState((s) => s.message);
  const messageId = message.id;
  const [rating, setRating] = useState<"positive" | "negative" | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const threadId = threadItem.remoteId;

  useEffect(() => {
    if (!identity.subject || !threadId || !messageId || messageId.startsWith("__optimistic__")) return;
    let active = true;
    void client.getFeedback(threadId, messageId).then(
      (feedback) => active && setRating(feedback.rating),
      (feedbackError) => {
        if (active && !(feedbackError instanceof Error && "status" in feedbackError && feedbackError.status === 404)) {
          setError("Unable to load feedback.");
        }
      },
    );
    return () => {
      active = false;
    };
  }, [client, identity.subject, messageId, threadId]);

  const submit = async (next: "positive" | "negative") => {
    if (!identity.subject || !threadId || !messageId || saving) return;
    const previous = rating;
    const retracted = rating === next;
    setSaving(true);
    setError(null);
    setRating(retracted ? null : next);
    try {
      if (retracted) {
        await client.deleteFeedback(threadId, messageId);
      } else {
        let feedback;
        try {
          feedback = await client.setFeedback(threadId, messageId, next);
        } catch (requestError) {
          // A user can rate before the debounced transcript write completes.
          // Only then append the exact UI message and retry once; appending
          // after it already exists could conflict on transient UI fields.
          if (!(requestError instanceof Error && "status" in requestError && requestError.status === 404)) {
            throw requestError;
          }
          await client.appendMessage(threadId, message);
          feedback = await client.setFeedback(threadId, messageId, next);
        }
        setRating(feedback.rating);
      }
    } catch {
      setRating(previous);
      setError("Unable to save feedback. Try again.");
    } finally {
      setSaving(false);
    }
  };

  if (!identity.subject || !threadId || !messageId || messageId.startsWith("__optimistic__")) return null;
  return (
    <div
      className="ml-1 flex items-center gap-1"
      aria-label="Message feedback"
      data-feedback-thread-id={threadId}
    >
      <TooltipIconButton
        tooltip="Helpful"
        aria-label="Mark response helpful"
        aria-pressed={rating === "positive"}
        disabled={saving}
        onClick={() => void submit("positive")}
      >
        <ThumbsUpIcon className={rating === "positive" ? "fill-current" : undefined} />
      </TooltipIconButton>
      <TooltipIconButton
        tooltip="Not helpful"
        aria-label="Mark response not helpful"
        aria-pressed={rating === "negative"}
        disabled={saving}
        onClick={() => void submit("negative")}
      >
        <ThumbsDownIcon className={rating === "negative" ? "fill-current" : undefined} />
      </TooltipIconButton>
      {error && <span role="alert" className="sr-only">{error}</span>}
    </div>
  );
};

const AssistantActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      autohideFloat="single-branch"
      className="aui-assistant-action-bar-root col-start-3 row-start-2 -ml-1 flex gap-1 text-muted-foreground data-floating:absolute data-floating:rounded-md data-floating:border data-floating:bg-background data-floating:p-1 data-floating:shadow-sm"
    >
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton tooltip="Copy">
          <MessagePrimitive.If copied>
            <CheckIcon />
          </MessagePrimitive.If>
          <MessagePrimitive.If copied={false}>
            <CopyIcon />
          </MessagePrimitive.If>
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Reload asChild>
        <TooltipIconButton tooltip="Refresh">
          <RefreshCwIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Reload>
    </ActionBarPrimitive.Root>
  );
};

const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root asChild>
      <div
        className="aui-user-message-root mx-auto grid w-full max-w-[var(--thread-max-width)] animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] gap-y-2 px-2 py-4 duration-150 ease-out fade-in slide-in-from-bottom-1 first:mt-3 last:mb-5 [&:where(>*)]:col-start-2"
        data-role="user"
      >
        <UserMessageAttachments />

        <div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
          <div className="aui-user-message-content rounded-3xl bg-muted px-5 py-2.5 break-words text-foreground">
            <MessagePrimitive.Parts />
          </div>
          <div className="aui-user-action-bar-wrapper absolute top-1/2 left-0 -translate-x-full -translate-y-1/2 pr-2">
            <UserActionBar />
          </div>
        </div>

        <BranchPicker className="aui-user-branch-picker col-span-full col-start-1 row-start-3 -mr-1 justify-end" />
      </div>
    </MessagePrimitive.Root>
  );
};

const UserActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="aui-user-action-bar-root flex flex-col items-end"
    >
      <ActionBarPrimitive.Edit asChild>
        <TooltipIconButton tooltip="Edit" className="aui-user-action-edit p-4">
          <PencilIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  );
};

const EditComposer: FC = () => {
  return (
    <div className="aui-edit-composer-wrapper mx-auto flex w-full max-w-[var(--thread-max-width)] flex-col gap-4 px-2 first:mt-4">
      <ComposerPrimitive.Root className="aui-edit-composer-root ml-auto flex w-full max-w-7/8 flex-col rounded-xl bg-muted">
        <ComposerPrimitive.Input
          className="aui-edit-composer-input flex min-h-[60px] w-full resize-none bg-transparent p-4 text-foreground outline-none"
          autoFocus
        />

        <div className="aui-edit-composer-footer mx-3 mb-3 flex items-center justify-center gap-2 self-end">
          <ComposerPrimitive.Cancel asChild>
            <Button variant="ghost" size="sm" aria-label="Cancel edit">
              Cancel
            </Button>
          </ComposerPrimitive.Cancel>
          <ComposerPrimitive.Send asChild>
            <Button size="sm" aria-label="Update message">
              Update
            </Button>
          </ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </div>
  );
};

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({
  className,
  ...rest
}) => {
  return (
    <BranchPickerPrimitive.Root
      hideWhenSingleBranch
      className={cn(
        "aui-branch-picker-root mr-2 -ml-2 inline-flex items-center text-xs text-muted-foreground",
        className
      )}
      {...rest}
    >
      <BranchPickerPrimitive.Previous asChild>
        <TooltipIconButton tooltip="Previous">
          <ChevronLeftIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Previous>
      <span className="aui-branch-picker-state font-medium">
        <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
      </span>
      <BranchPickerPrimitive.Next asChild>
        <TooltipIconButton tooltip="Next">
          <ChevronRightIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Next>
    </BranchPickerPrimitive.Root>
  );
};
 
