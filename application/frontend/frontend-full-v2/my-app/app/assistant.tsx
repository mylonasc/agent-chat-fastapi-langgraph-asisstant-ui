"use client";

import React, { useEffect, useMemo } from "react";
import  MyRuntimeProvider  from "./MyRuntimeProvider";
import { Thread } from "@/components/assistant-ui/thread";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Separator } from "@/components/ui/separator";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { ThreadListPrimitive, useAssistantState } from "@assistant-ui/react";

function ActiveThreadScope({ children }: { children: React.ReactNode }) {
  const prim: any = ThreadListPrimitive as any;
  const Scope = useMemo(() => prim.Active ?? prim.ActiveItem ?? null, [prim]);

  useEffect(() => {
    console.log("[ActiveThreadScope] using:", Scope ? (prim.Active ? "Active" : "ActiveItem") : "NONE");
  }, [Scope, prim.Active]);

  return Scope ? <Scope>{children}</Scope> : <>{children}</>;
}

function MinimalProbe() {
  const threadsStore = useAssistantState((s) => (s as any).threads ?? null);
  const threadStore = useAssistantState((s) => (s as any).thread ?? null);

  console.log("[MinimalProbe] render", {
    mainThreadId: threadsStore?.mainThreadId,
    threadIds: threadsStore?.threadIds,
    threadId: threadStore?.threadId,
    messagesLen: threadStore?.messages?.length ?? 0,
  });

  return null;
}

export const Assistant = () => {
  useEffect(() => console.log("[Assistant] mounted"), []);

  return (
    <MyRuntimeProvider>
      <ThreadListPrimitive.Root className="aui-root aui-app-root">
        <MinimalProbe />

        <SidebarProvider>
          <div className="flex h-dvh w-full pr-0.5">
            <ThreadListSidebar />

            <SidebarInset>
              <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
                <SidebarTrigger />
                <Separator orientation="vertical" className="mr-2 h-4" />
                <Breadcrumb />
              </header>

              <div className="flex-1 overflow-hidden">
                <ActiveThreadScope>
                  <Thread />
                </ActiveThreadScope>
              </div>
            </SidebarInset>
          </div>
        </SidebarProvider>
      </ThreadListPrimitive.Root>
    </MyRuntimeProvider>
  );
};
