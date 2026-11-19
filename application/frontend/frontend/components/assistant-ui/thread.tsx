"use client";

import { ThreadPrimitive } from "@assistant-ui/react";
import { domAnimation, LazyMotion, MotionConfig } from "motion/react";
import type { FC } from "react";

import { AutoThreadTitle } from "@/features/thread/auto-title";
import { EnsureThreadInitialized } from "@/features/thread/ensure-initialized";
import { RememberRemoteThread } from "@/features/thread/remember-remote-thread";
import { TranscriptSynchronizer } from "@/features/thread/transcript-synchronizer";
import {
  StatusPanelHost,
  ToolUiHost,
} from "@/features/registry/registry-hosts";

import { Composer, EditComposer } from "./thread-composer";
import { ThreadRunError } from "./thread-errors";
import { ThreadHeader } from "./thread-header";
import { AssistantMessage, UserMessage } from "./thread-messages";
import { StarterPage } from "./thread-starter";

/**
 * Thread composition root.
 *
 * Presentational regions live in sibling modules under
 * `components/assistant-ui`; cross-remount behaviors live in
 * `features/thread`; tool UIs and status panels are contributions mounted
 * from the capability registry; feedback and RAG live in their feature
 * folders.
 */
export const Thread: FC = () => {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <ThreadPrimitive.Root
          className="aui-root aui-thread-root @container flex h-full flex-col bg-background"
          style={{
            ["--thread-max-width" as string]: "44rem",
          }}
        >
          <ThreadHeader />

          <ToolUiHost />
          <AutoThreadTitle />
          <RememberRemoteThread />
          <EnsureThreadInitialized />
          <TranscriptSynchronizer />

          <ThreadPrimitive.Viewport className="aui-thread-viewport relative flex flex-1 flex-col overflow-x-auto overflow-y-scroll px-4">
            <ThreadPrimitive.If empty>
              <StarterPage />
            </ThreadPrimitive.If>

            <ThreadPrimitive.Messages
              components={{
                UserMessage,
                EditComposer,
                AssistantMessage,
              }}
            />

            <StatusPanelHost />

            <ThreadPrimitive.If empty={false}>
              <div className="aui-thread-viewport-spacer min-h-8 grow" />
            </ThreadPrimitive.If>

            <ThreadRunError />

            <Composer />
          </ThreadPrimitive.Viewport>
        </ThreadPrimitive.Root>
      </MotionConfig>
    </LazyMotion>
  );
};
