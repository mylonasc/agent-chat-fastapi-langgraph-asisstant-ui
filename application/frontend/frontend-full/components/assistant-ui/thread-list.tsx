// components/assistant-ui/thread-list.tsx
import type { FC } from "react";
import {
  useAssistantApi,
  ThreadListItemPrimitive,
  ThreadListPrimitive,
  useAssistantState,
} from "@assistant-ui/react";
import { ArchiveIcon, PencilIcon, PlusIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Skeleton } from "@/components/ui/skeleton";

export const ThreadList: FC = () => {
  // ✅ Root is now provided by Assistant.tsx
  return (
    
    <ThreadListPrimitive.Root className="aui-thread-list-root flex flex-col items-stretch gap-1.5">
    <div className="aui-thread-list-root flex flex-col items-stretch gap-1.5">
      <ThreadListNew />
      <ThreadListItems />
    </div>
    </ThreadListPrimitive.Root>    
  );
};

const ThreadListNew: FC = () => {
  return (
    <ThreadListPrimitive.New asChild>
      <Button
        className="aui-thread-list-new flex items-center justify-start gap-1 rounded-lg px-2.5 py-2 text-start hover:bg-muted data-active:bg-muted"
        variant="ghost"
      >
        <PlusIcon />
        New Thread
      </Button>
    </ThreadListPrimitive.New>
  );
};

const ThreadListItems: FC = () => {
  const isLoading = useAssistantState((s) => !!(s as any).threads?.isLoading);

  if (isLoading) return <ThreadListSkeleton />;
  return <ThreadListPrimitive.Items components={{ ThreadListItem }} />;
};

const ThreadListSkeleton: FC = () => {
  return (
    <>
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          role="status"
          aria-label="Loading threads"
          aria-live="polite"
          className="aui-thread-list-skeleton-wrapper flex items-center gap-2 rounded-md px-3 py-2"
        >
          <Skeleton className="aui-thread-list-skeleton h-[22px] flex-grow" />
        </div>
      ))}
    </>
  );
};

const ThreadListItem: FC = () => {
  const api = useAssistantApi();
  const title = useAssistantState((s) => s.threadListItem.title ?? "New Chat");

  const renameChat = () => {
    const next = window.prompt("Rename chat", title);
    if (next == null) return;
    const trimmed = next.trim();
    if (!trimmed || trimmed === title) return;
    api.threadListItem().rename(trimmed);
  };

  return (
    <ThreadListItemPrimitive.Root className="aui-thread-list-item flex items-center gap-2 rounded-lg transition-all hover:bg-muted focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none data-active:bg-muted">
      <ThreadListItemPrimitive.Trigger className="aui-thread-list-item-trigger flex-grow px-3 py-2 text-start">
        <span className="aui-thread-list-item-title text-sm">
          <ThreadListItemPrimitive.Title fallback="New Chat" />
        </span>
      </ThreadListItemPrimitive.Trigger>

      <TooltipIconButton
        className="aui-thread-list-item-rename size-4 p-0 text-foreground hover:text-primary"
        variant="ghost"
        tooltip="Rename thread"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          renameChat();
        }}
      >
        <PencilIcon />
      </TooltipIconButton>

      <ThreadListItemPrimitive.Archive asChild>
        <TooltipIconButton
          className="aui-thread-list-item-archive mr-3 ml-auto size-4 p-0 text-foreground hover:text-primary"
          variant="ghost"
          tooltip="Archive thread"
        >
          <ArchiveIcon />
        </TooltipIconButton>
      </ThreadListItemPrimitive.Archive>
    </ThreadListItemPrimitive.Root>
  );
};
