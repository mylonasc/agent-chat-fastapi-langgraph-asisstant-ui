"use client";

import { useAssistantState } from "@assistant-ui/react";
import { useCallback, useEffect, useState } from "react";

import { useApiClient } from "@/hooks/use-api-client";
import { ApiError, type FeedbackRating } from "@/lib/api-client";

export type MessageFeedbackState = {
  canFeedback: boolean;
  threadId: string | undefined;
  rating: FeedbackRating | null;
  saving: boolean;
  error: string | null;
  submit: (next: FeedbackRating) => Promise<void>;
};

/**
 * Load and persist the current message's feedback rating.
 *
 * Gated on loaded because the pre-config client points at the build-time
 * fallback base, whose 404s would mask real stored ratings.
 */
export function useMessageFeedback(): MessageFeedbackState {
  const { config, client, identity, loaded } = useApiClient();
  const threadItem = useAssistantState((state) => state.threadListItem);
  const message = useAssistantState((state) => state.message);
  const messageId = message.id;
  const threadId = config.features.threads ? threadItem?.remoteId : undefined;
  const [rating, setRating] = useState<FeedbackRating | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Feedback rows are stored against transcript messages, so both the
  // thread-list and transcript capabilities must exist. A threadless
  // transport runtime still exposes a local thread id; rating it would
  // target a session the backend never created.
  const canFeedback = Boolean(
    config.features.threads &&
    config.features.transcripts &&
    identity.subject &&
    threadId &&
    messageId &&
    !messageId.startsWith("__optimistic__"),
  );

  useEffect(() => {
    if (!loaded || !canFeedback || !threadId || !messageId) return;
    let active = true;
    void client.feedback.get(threadId, messageId).then(
      (feedback) => active && setRating(feedback.rating),
      (feedbackError) => {
        if (
          active &&
          !(feedbackError instanceof ApiError && feedbackError.status === 404)
        ) {
          setError("Unable to load feedback.");
        }
      },
    );
    return () => {
      active = false;
    };
  }, [canFeedback, client, identity.subject, loaded, messageId, threadId]);

  const submit = useCallback(
    async (next: FeedbackRating) => {
      if (
        !loaded ||
        !canFeedback ||
        !identity.subject ||
        !threadId ||
        !messageId ||
        saving
      ) {
        return;
      }
      const previous = rating;
      const retracted = rating === next;
      setSaving(true);
      setError(null);
      setRating(retracted ? null : next);
      try {
        if (retracted) {
          await client.feedback.remove(threadId, messageId);
        } else {
          let feedback;
          try {
            feedback = await client.feedback.upsert(threadId, messageId, next);
          } catch (requestError) {
            // A user can rate before the debounced transcript write completes.
            // Only then append the exact UI message and retry once; appending
            // after it already exists could conflict on transient UI fields.
            if (
              !(requestError instanceof ApiError && requestError.status === 404)
            ) {
              throw requestError;
            }
            await client.transcripts.append(threadId, message);
            feedback = await client.feedback.upsert(threadId, messageId, next);
          }
          setRating(feedback.rating);
        }
      } catch {
        setRating(previous);
        setError("Unable to save feedback. Try again.");
      } finally {
        setSaving(false);
      }
    },
    [
      canFeedback,
      client,
      identity.subject,
      loaded,
      message,
      messageId,
      rating,
      saving,
      threadId,
    ],
  );

  return { canFeedback, threadId, rating, saving, error, submit };
}
