"use client";

import { ThumbsDownIcon, ThumbsUpIcon } from "lucide-react";
import type { FC } from "react";

import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";

import { useMessageFeedback } from "./use-message-feedback";

/** Positive/negative rating controls for the current assistant message. */
export const MessageFeedbackControls: FC = () => {
  const { canFeedback, threadId, rating, saving, error, submit } =
    useMessageFeedback();

  if (!canFeedback || !threadId) return null;

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
        <ThumbsUpIcon
          className={rating === "positive" ? "fill-current" : undefined}
        />
      </TooltipIconButton>
      <TooltipIconButton
        tooltip="Not helpful"
        aria-label="Mark response not helpful"
        aria-pressed={rating === "negative"}
        disabled={saving}
        onClick={() => void submit("negative")}
      >
        <ThumbsDownIcon
          className={rating === "negative" ? "fill-current" : undefined}
        />
      </TooltipIconButton>
      {error && (
        <span role="alert" className="sr-only">
          {error}
        </span>
      )}
    </div>
  );
};
