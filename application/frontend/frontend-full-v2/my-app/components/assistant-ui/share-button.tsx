"use client";

import { useAssistantState } from "@assistant-ui/react";
import { ShareIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export const ShareButton = () => {
  // 1. Return primitives directly to avoid "infinite loop" error
  
  const threadId = useAssistantState((s) => s.thread.threadId);
  const messageCount = useAssistantState((s) => s.thread.messages.length);

  const handleShare = () => {
    // Debug check: If you see "new" here after a message is sent, 
    // it means the backend response hasn't updated the runtime ID yet.
    console.log("Current Thread ID:", threadId);

    if (!threadId || threadId === "new") {
      alert("Please wait for the conversation to initialize.");
      return;
    }

    if (messageCount === 0) {
      alert("You must start a conversation before sharing.");
      return;
    }

    const url = `${window.location.origin}/share/${threadId}`;
    navigator.clipboard.writeText(url);
    alert("Link copied to clipboard!");
  };

  // Only show the button if there are messages
  if (messageCount === 0) return null;

  return (
    <Button 
      variant="ghost" 
      size="icon" 
      onClick={handleShare}
      className="size-8"
      title="Share conversation"
    >
      <ShareIcon className="size-4" />
    </Button>
  );
};