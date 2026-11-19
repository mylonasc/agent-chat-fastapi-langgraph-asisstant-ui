"use client";

import { ThreadPrimitive } from "@assistant-ui/react";
import { useEffect, useState, type FC } from "react";
import * as m from "motion/react-m";

import { Button } from "@/components/ui/button";
import { useApiClient } from "@/hooks/use-api-client";
import { useEnsureThreadInitialized } from "@/features/thread/ensure-initialized";

type Suggestion = { id: string; label: string; prompt: string };

/**
 * Starter page: every empty thread (launch, New Thread, post-archive
 * landing) shows this hero panel instead of an empty chat, naming the
 * agent the first message will go to. Suggestion cards send into the
 * pending thread.
 */
export const StarterPage: FC = () => {
  const { canSend, isInitializing } = useEnsureThreadInitialized();
  const { config, client, loaded } = useApiClient();
  const presentation = config.presentation;
  const [defaultAgent, setDefaultAgent] = useState<string | null>(null);

  useEffect(() => {
    if (!loaded || !config.features.agents) {
      setDefaultAgent(null);
      return;
    }
    let live = true;
    void client.agents.list().then(
      (data) => {
        if (live) {
          setDefaultAgent(data.default);
        }
      },
      () => {
        if (live) setDefaultAgent(null);
      },
    );
    return () => {
      live = false;
    };
  }, [client, loaded, config.features.agents]);

  return (
    <div className="aui-starter-page mx-auto my-auto flex w-full max-w-[var(--thread-max-width)] flex-grow flex-col items-center justify-center px-8">
      <div className="aui-starter-page-card flex w-full flex-col items-center gap-3 rounded-3xl border bg-muted/40 px-8 py-10 text-center">
        <p className="aui-starter-page-eyebrow text-xs font-semibold tracking-widest text-muted-foreground uppercase">
          New conversation
        </p>
        <h1 className="aui-starter-page-heading text-3xl font-semibold">
          Start chatting with agent:{" "}
          <span className="aui-starter-page-agent rounded-md bg-background px-2 py-0.5 font-mono">
            {defaultAgent ?? (loaded ? "default" : "…")}
          </span>
        </h1>
        <p className="aui-starter-page-description max-w-md text-sm text-muted-foreground">
          {presentation.welcome_description}
        </p>
      </div>

      {!canSend && (
        <div className="aui-starter-page-status mt-4 text-sm text-muted-foreground">
          {isInitializing ? "Initializing chat…" : "Preparing chat…"}
        </div>
      )}

      <div className="aui-starter-page-suggestions mt-6 w-full">
        <ThreadSuggestions
          disabled={!canSend}
          questions={presentation.questions}
        />
      </div>
    </div>
  );
};

const ThreadSuggestions: FC<{
  disabled?: boolean;
  questions: readonly Suggestion[];
}> = ({ disabled, questions }) => {
  return (
    <div className="aui-thread-welcome-suggestions grid w-full gap-2 pb-4 @md:grid-cols-2">
      {questions.map((suggestedAction, index) => (
        <m.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ delay: 0.05 * index }}
          key={suggestedAction.id}
          className="aui-thread-welcome-suggestion-display [&:nth-child(n+3)]:hidden @md:[&:nth-child(n+3)]:block"
        >
          <ThreadPrimitive.Suggestion
            prompt={suggestedAction.prompt}
            send={!disabled}
            asChild
          >
            <Button
              variant="ghost"
              disabled={disabled}
              className="aui-thread-welcome-suggestion h-auto w-full flex-1 flex-wrap items-start justify-start gap-1 rounded-3xl border px-5 py-4 text-left text-sm @md:flex-col dark:hover:bg-accent/60"
              aria-label={suggestedAction.prompt}
            >
              <span className="aui-thread-welcome-suggestion-text-1 font-medium">
                {suggestedAction.label}
              </span>
              <span className="aui-thread-welcome-suggestion-text-2 text-muted-foreground">
                {suggestedAction.prompt}
              </span>
            </Button>
          </ThreadPrimitive.Suggestion>
        </m.div>
      ))}
    </div>
  );
};
