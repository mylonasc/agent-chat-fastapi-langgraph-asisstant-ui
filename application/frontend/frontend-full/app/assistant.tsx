"use client";

import React, { useEffect } from "react";
import  MyRuntimeProvider  from "./MyRuntimeProvider";
import { Thread } from "@/components/assistant-ui/thread";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Separator } from "@/components/ui/separator";
import { Breadcrumb } from "@/components/ui/breadcrumb";

export const Assistant = () => {
  useEffect(() => console.log("[Assistant] mounted"), []);

  return (
    <MyRuntimeProvider>
      {/* <RuntimeInspector /> */}
        {/* <MinimalProbe /> */}
      
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
                  
                    {/* <RuntimeDebugProbe /> */}
                    <Thread />
              </div>
              
            </SidebarInset>
          </div>
          
        </SidebarProvider>
        
    </MyRuntimeProvider>
  );
};
