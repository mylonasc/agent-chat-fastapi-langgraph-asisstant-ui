"use client";

import { Thread } from "@/components/assistant-ui/thread";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { useApiClient } from "@/hooks/use-api-client";

import MyRuntimeProvider from "./MyRuntimeProvider";

export const Assistant = () => {
  const { config } = useApiClient();
  const threadsEnabled = config.features.threads;

  return (
    <MyRuntimeProvider>
      <SidebarProvider>
        <div className="flex h-dvh w-full pr-0.5">
          {threadsEnabled && <ThreadListSidebar />}

          <SidebarInset>
            <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
              {threadsEnabled && (
                <>
                  <SidebarTrigger />
                  <Separator orientation="vertical" className="mr-2 h-4" />
                </>
              )}
              <Breadcrumb />
            </header>

            <div className="flex-1 overflow-hidden">
              <Thread />
            </div>
          </SidebarInset>
        </div>
      </SidebarProvider>
    </MyRuntimeProvider>
  );
};
