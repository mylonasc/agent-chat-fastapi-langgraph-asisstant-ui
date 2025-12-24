
// app/share/[threadId]/page.tsx
"use client";
import { AssistantRuntimeProvider, useExternalStoreRuntime } from "@assistant-ui/react";
import { Thread } from "@/components/assistant-ui/thread";
import { useEffect, useState } from "react";

export default function SharedThreadPage({ params }: { params: { threadId: string } }) {
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    fetch(`http://localhost:8010/public/threads/${params.threadId}`)
      .then(res => res.json())
      .then(data => setMessages(data.messages));
  }, [params.threadId]);

  // Use ExternalStoreRuntime for a read-only view
  const runtime = useExternalStoreRuntime({
    messages,
    // Disable all mutations to make it read-only
    onNew: async () => {}, 
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="h-dvh w-full max-w-3xl mx-auto p-4">
        {/* Pass components={{ Composer: () => null }} to hide the input */}
        <Thread components={{ Composer: () => null }} />
      </div>
    </AssistantRuntimeProvider>
  );
}
