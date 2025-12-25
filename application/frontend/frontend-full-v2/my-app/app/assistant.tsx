"use client";

import React, { useEffect, useMemo , useState} from "react";
import  MyRuntimeProvider  from "./MyRuntimeProvider";
import { Thread } from "@/components/assistant-ui/thread";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Separator } from "@/components/ui/separator";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { ThreadListPrimitive, useAssistantState, AssistantRuntimeProvider } from "@assistant-ui/react";


import { useAssistantRuntime  } from "@assistant-ui/react";

export const RuntimeInspector = () => {
  const runtime = useAssistantRuntime();

  useEffect(() => {
    console.group("🕵️ SAFE RUNTIME INSPECTION");
    
    if (!runtime) {
      console.error("Runtime is null/undefined");
      console.groupEnd();
      return;
    }

    // 1. Log top-level keys
    console.log("Runtime Keys:", Object.keys(runtime));

    // 2. Check for specific known properties safely
    const r = runtime as any;
    
    console.log("Has .threads?", !!r.threads);
    console.log("Has .thread?", !!r.thread);
    console.log("Has .main?", !!r.main);
    
    // 3. If .thread exists, what is it?
    if (r.thread) {
        console.log("runtime.thread:", r.thread);
        console.log("runtime.thread.getState?", typeof r.thread.getState);
    }

    console.groupEnd();
  }, [runtime]);

  return null; // Render nothing
};

export function RuntimeDebugProbe() {
  const [isOpen, setIsOpen] = useState(true); // Default open to see immediately
  
  const runtime = useAssistantRuntime();
  const threadState = useAssistantState((s) => s.thread);
  const messages = useAssistantState((s) => s.thread.messages);
  
  const internalThreadId = (runtime as any)?.thread?.id;
  const visibleThreadId = threadState.threadId;
  const msgCount = messages?.length ?? 0;

  const containerStyle: React.CSSProperties = {
    position: "absolute",
    top: "10px",
    right: "10px",
    width: "350px",
    maxHeight: "80vh",
    overflowY: "auto",
    padding: "12px",
    backgroundColor: msgCount > 0 ? "#f0fff4" : "#fff0f0", // Green if msgs exist, Red if empty
    border: `2px solid ${msgCount > 0 ? "#48bb78" : "#f56565"}`,
    borderRadius: "8px",
    fontSize: "11px",
    fontFamily: "monospace",
    color: "#333",
    zIndex: 9999,
    boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
  };

  return (
    <div style={containerStyle}>
      <div 
        style={{ cursor: "pointer", fontWeight: "bold", marginBottom: "8px" }} 
        onClick={() => setIsOpen(!isOpen)}
      >
        [DEBUG] {isOpen ? "▼" : "▶"} {msgCount} Msgs 
        {msgCount === 0 && " (EMPTY)"}
      </div>

      {isOpen && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5px", marginBottom: "8px" }}>
            <div><strong>Runtime:</strong> {runtime ? "✅ OK" : "❌ NULL"}</div>
            <div><strong>Loading:</strong> {(threadState as any).isLoading ? "⏳" : "—"}</div>
            <div><strong>UI ID:</strong> <span style={{color: "blue"}}>{visibleThreadId}</span></div>
            <div><strong>Run ID:</strong> <span style={{color: "green"}}>{internalThreadId}</span></div>
          </div>

          <hr style={{ margin: "8px 0", borderColor: "#ddd" }}/>

          {msgCount === 0 ? (
            <div style={{ color: "#c53030", fontStyle: "italic" }}>
              Messages not loaded or import failed.
            </div>
          ) : (
            <ul style={{ paddingLeft: "10px", margin: 0 }}>
              {messages.map((m, i) => (
                <li key={m.id} style={{ marginBottom: "8px", borderBottom: "1px dashed #eee", paddingBottom: "4px" }}>
                  <strong>[{i}] {m.role}</strong> <span style={{color:"#888"}}>({m.id.slice(0,5)}...)</span>
                  
                  {/* Show content preview */}
                  <div style={{ marginTop: "2px", color: "#444" }}>
                    {m.content.map((c, ci) => (
                       <span key={ci}>
                         {c.type === "text" ? (c as any).text.slice(0, 50) + "..." : "[Attach]"}
                       </span>
                    ))}
                  </div>
                  
                  {/* Detailed JSON dump for debugging structure */}
                  <details style={{ marginTop: "4px" }}>
                    <summary style={{ cursor: "pointer", color: "#666" }}>Raw JSON</summary>
                    <pre style={{ fontSize: "9px", backgroundColor: "#eee", padding: "4px", borderRadius: "4px" }}>
                      {JSON.stringify(m, null, 2)}
                    </pre>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
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


// Simple Guard Component to handle the "undefined" state during reload/select
function ThreadContextGuard({ children }: { children: React.ReactNode }) {
  const { useAssistantState } = require("@assistant-ui/react"); // late import or top-level
  const mainThreadId = useAssistantState((s: any) => s.threads?.mainThreadId);

  if (!mainThreadId) {
    return <div className="h-full flex items-center justify-center text-muted-foreground">Select a chat...</div>;
  }
  
  return <div key={mainThreadId} className="h-full">{children}</div>;
}

export const Assistant = () => {
  useEffect(() => console.log("[Assistant] mounted"), []);

  return (
    <MyRuntimeProvider>
      <RuntimeInspector />
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
                  
                  {/* <ThreadContextGuard> */}
                    <RuntimeDebugProbe />
                    <Thread />
                  {/* </ThreadContextGuard> */}
              </div>
              
            </SidebarInset>
          </div>
          
        </SidebarProvider>
        
    </MyRuntimeProvider>
  );
};
