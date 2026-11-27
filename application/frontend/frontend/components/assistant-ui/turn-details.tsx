"use client";

import {
  MessagePrimitive,
  ThreadPrimitive,
  useAssistantState,
  type ToolCallMessagePartComponent,
} from "@assistant-ui/react";
import { PanelRightOpenIcon, XIcon } from "lucide-react";
import {
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useIsMobile } from "@/hooks/use-mobile";

import { ToolFallback } from "./tool-fallback";

type Selection = { threadId: string; messageId: string };
type TurnDetailsContextValue = {
  panelId: string;
  selection: Selection | null;
  open: (messageId: string, trigger: HTMLButtonElement) => void;
  close: () => void;
  restoreFocus: () => void;
};

const TurnDetailsContext = createContext<TurnDetailsContextValue | null>(null);

/** Opt-in so the minimal preset keeps its inline tool UIs. */
export function TurnDetailsProvider({
  enabled,
  children,
}: {
  enabled: boolean;
  children: ReactNode;
}) {
  const panelId = useId();
  const threadId = useAssistantState(
    (state) => state.threadListItem?.id ?? "single-thread",
  );
  const [selection, setSelection] = useState<Selection | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const restoreFocus = () => {
    if (triggerRef.current?.isConnected) triggerRef.current.focus();
  };

  return (
    <TurnDetailsContext.Provider
      value={
        enabled
          ? {
              panelId,
              selection: selection?.threadId === threadId ? selection : null,
              open: (messageId, trigger) => {
                triggerRef.current = trigger;
                setSelection({ threadId, messageId });
              },
              close: () => {
                setSelection(null);
                restoreFocus();
              },
              restoreFocus,
            }
          : null
      }
    >
      {children}
    </TurnDetailsContext.Provider>
  );
}

export const useTurnDetails = () => useContext(TurnDetailsContext);

export const HiddenToolCall: ToolCallMessagePartComponent = () => null;

export function ShowTurnDetails() {
  const details = useTurnDetails();
  const messageId = useAssistantState((state) => state.message.id);
  if (!details) return null;

  const isSelected = details.selection?.messageId === messageId;
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="aui-show-turn-details gap-1.5 text-muted-foreground"
      aria-expanded={isSelected}
      aria-controls={isSelected ? details.panelId : undefined}
      onClick={(event) => details.open(messageId, event.currentTarget)}
    >
      <PanelRightOpenIcon aria-hidden="true" className="size-4" />
      Show details
    </Button>
  );
}

const DetailsFallback: ToolCallMessagePartComponent = (props) => (
  <ToolFallback {...props} initiallyExpanded />
);

/** Keep message/part scopes intact for registered, interactive tool UIs. */
function TurnToolParts() {
  const content = useAssistantState((state) => state.message.content);
  const messageId = useAssistantState((state) => state.message.id);
  return content.map((part, index) =>
    part.type === "tool-call" ? (
      <MessagePrimitive.PartByIndex
        key={`${messageId}-${part.toolCallId}`}
        index={index}
        components={{ tools: { Fallback: DetailsFallback } }}
      />
    ) : null,
  );
}

const toolMessageComponents = { Message: TurnToolParts };

function DesktopPanel({
  panelId,
  messageId,
  close,
  children,
}: {
  panelId: string;
  messageId: string;
  close: () => void;
  children: ReactNode;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, [messageId]);

  return (
    <aside
      id={panelId}
      aria-labelledby={`${panelId}-title`}
      data-testid="turn-details-sidebar"
      className="aui-turn-details flex h-full w-96 max-w-[45%] min-w-0 shrink-0 flex-col border-l bg-background"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          close();
        }
      }}
    >
      <div className="flex shrink-0 items-center justify-between border-b p-4">
        <h2
          id={`${panelId}-title`}
          ref={headingRef}
          tabIndex={-1}
          className="font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Turn details
        </h2>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Close turn details"
          onClick={close}
        >
          <XIcon aria-hidden="true" className="size-4" />
        </Button>
      </div>
      {children}
    </aside>
  );
}

export function TurnDetailsSidebar() {
  const details = useTurnDetails();
  const messages = useAssistantState((state) => state.thread.messages);
  const isMobile = useIsMobile();
  const selectedIndex = messages.findIndex(
    (message) => message.id === details?.selection?.messageId,
  );
  // Branch changes and thread switches must never display an unrelated turn.
  if (!details?.selection || selectedIndex < 0) return null;

  let start = selectedIndex;
  while (start > 0 && messages[start - 1]?.role !== "user") start--;
  let end = selectedIndex + 1;
  while (end < messages.length && messages[end]?.role !== "user") end++;
  const turnMessages = messages.slice(start, end);
  const toolCount = turnMessages.reduce(
    (count, message) =>
      count +
      message.content.filter((part) => part.type === "tool-call").length,
    0,
  );
  const prompt = messages[start - 1]?.content
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join(" ");
  const body = (
    <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto p-4 [overflow-wrap:anywhere]">
      {prompt && (
        <p className="mb-2 line-clamp-2 text-sm text-muted-foreground">
          {prompt}
        </p>
      )}
      <p className="mb-4 text-xs text-muted-foreground" aria-live="polite">
        {toolCount} tool {toolCount === 1 ? "call" : "calls"}
      </p>
      {toolCount === 0 ? (
        <p className="text-sm text-muted-foreground">
          No tool calls were made in this turn.
        </p>
      ) : (
        turnMessages.map((message, offset) =>
          message.role === "assistant" ? (
            <ThreadPrimitive.MessageByIndex
              key={message.id}
              index={start + offset}
              components={toolMessageComponents}
            />
          ) : null,
        )
      )}
    </div>
  );

  if (isMobile) {
    return (
      <Sheet open onOpenChange={(open) => !open && details.close()}>
        <SheetContent
          id={details.panelId}
          side="right"
          data-testid="turn-details-sidebar"
          className="w-[min(100%,24rem)] gap-0"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            details.restoreFocus();
          }}
        >
          <SheetHeader className="shrink-0 border-b pr-12">
            <SheetTitle>Turn details</SheetTitle>
            <SheetDescription>
              Tool calls and results for this turn.
            </SheetDescription>
          </SheetHeader>
          {body}
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <DesktopPanel
      panelId={details.panelId}
      messageId={details.selection.messageId}
      close={details.close}
    >
      {body}
    </DesktopPanel>
  );
}
