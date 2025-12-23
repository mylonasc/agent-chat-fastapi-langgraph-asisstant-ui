"use client";

import { AssistantRuntimeProvider, useAssistantTransportRuntime } from "@assistant-ui/react";
import { MyRuntimeProvider, converter } from "./MyRuntimeProvider";
// import { useLocalRuntime } from "@assistant-ui/react"
import {
  useChatRuntime,
  AssistantChatTransport,
} from "@assistant-ui/react-ai-sdk";
import { Thread } from "@/components/assistant-ui/thread";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Separator } from "@/components/ui/separator";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

export const Assistant = () => {

const runtime = useAssistantTransportRuntime({
    initialState: {
      messages: [],
    },
    api: "http://localhost:8010/assistant",
    converter,
    // 1. Pass the current threadId to the backend
    body: (thread) => ({
      thread_id: thread.threadId, 
      user_id : 'default_user'
    }),
    // 2. Handle switching threads
    onSwitchToNewThread: async (runtime) => {
      runtime.switchToThread(null); // Clears local state for a new thread
    },
    onSwitchToThread: async (threadId, runtime) => {
      // Fetch history from your backend endpoint: /threads/{thread_id}/messages
      const res = await fetch(`http://localhost:8010/threads/${threadId}/messages`);
      const data = await res.json();
      
      // Load the messages into the UI
      runtime.switchToThread(threadId, {
        messages: data.messages, 
      });
    },
    threads: {
    // 1. Tell assistant-ui how to fetch the list of threads for the sidebar
      fetchThreads: async () => {
        const res = await fetch("http://localhost:8010/threads?user_id=default_user");
        const threads = await res.json();
        return threads.map((t: any) => ({
          threadId: t.id,
          title: t.title || "New Chat",
        }));
      },
      // 2. (Optional) Handle deletions
      removeThread: async (threadId) => {
         await fetch(`http://localhost:8010/threads/${threadId}`, { method: 'DELETE' });
      }
    }
  });
  
  
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SidebarProvider>
        <div className="flex h-dvh w-full pr-0.5">
          <ThreadListSidebar />
          <SidebarInset>
            <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
              <SidebarTrigger />
              <Separator orientation="vertical" className="mr-2 h-4" />
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem className="hidden md:block">
                    <BreadcrumbLink
                      href="https://www.assistant-ui.com/docs/getting-started"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Build Your Own ChatGPT UX
                    </BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator className="hidden md:block" />
                  <BreadcrumbItem>
                    <BreadcrumbPage>Starter Template</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
            </header>
            <div className="flex-1 overflow-hidden">
              <Thread />
            </div>
          </SidebarInset>
        </div>
      </SidebarProvider>
    </AssistantRuntimeProvider>
  );
};
