## About
This documentation details the architecture and implementation of custom runtimes in `assistant-ui`, specifically focusing on **RemoteThreadListRuntime** (for managing thread lists/databases) and **AssistantTransportRuntime** (for managing individual chat thread logic), and how they handle state management.

---

## **1. Architecture Overview**

`assistant-ui` operates on a layered architecture designed to separate UI from state and logic.

* **UI Layer (Components):** Dumb React components (Shadcn-based) that render data. They do not manage state directly; they read from the Runtime.
* **Runtime Layer (State Management):** The "brain" of the application. It manages `isLoading`, `messages`, `threadId`, and streaming status.
* **Adapter Layer:** The bridge between the Runtime and your backend.
* `ThreadListAdapter`: Connects to your database to list/create/delete threads.
* `ModelAdapter` / `Transport`: Connects to your LLM API to send messages and receive streams.



### **State Management Flow**

The **`AssistantRuntime`** acts as the central store (similar to a Redux store or Context Provider).

1. **User Action:** User clicks "New Thread".
2. **Runtime Interception:** `RemoteThreadListRuntime` intercepts this, calls your `adapter.initialize()`, and waits for a Remote ID.
3. **State Update:** The Runtime updates the internal state to "Thread Created" and switches the active thread context.
4. **Transport Trigger:** When the user types, the **Thread Runtime** (often `AssistantTransportRuntime`) takes over, creating an optimistic message update and triggering the network request.

---

## **2. RemoteThreadListRuntime**

**Purpose:** Defines how your application lists, creates, renames, and archives chat threads in your custom database.

This is not a single source file you "find," but a **runtime hook** (`useRemoteThreadListRuntime`) that you must implement using an **Adapter Interface**.

### **Source Code / Reference Implementation**

Below is the boilerplate code you would write to implement this runtime.

```typescript
import { 
  useLocalRuntime, 
  useRemoteThreadListRuntime,
  type RemoteThreadListAdapter,
  type RemoteThreadMetadata 
} from "@assistant-ui/react";

// 1. Define your Adapter
const threadListAdapter: RemoteThreadListAdapter = {
  // Fetch the list of threads from your DB
  list: async (): Promise<{ threads: RemoteThreadMetadata[] }> => {
    const response = await fetch("/api/threads");
    return await response.json(); 
    // Expected format: { threads: [{ remoteId: "t_1", title: "Chat 1" }] }
  },

  // Create a new thread in your DB
  initialize: async (localId: string): Promise<{ remoteId: string }> => {
    const response = await fetch("/api/threads", {
      method: "POST",
      body: JSON.stringify({ localId }),
    });
    // CRITICAL: Return the database ID (remoteId) so the UI knows where to save messages
    return await response.json(); 
  },

  // Rename a thread
  rename: async (remoteId: string, newTitle: string): Promise<void> => {
    await fetch(`/api/threads/${remoteId}/rename`, {
      method: "PATCH",
      body: JSON.stringify({ title: newTitle }),
    });
  },

  // Archive/Delete
  delete: async (remoteId: string): Promise<void> => {
    await fetch(`/api/threads/${remoteId}`, { method: "DELETE" });
  },
  
  archive: async (remoteId: string): Promise<void> => { /* implementation */ },
  unarchive: async (remoteId: string): Promise<void> => { /* implementation */ },
};

// 2. The React Hook Component
export function MyDatabaseRuntime() {
  // This hook connects your adapter to the assistant-ui state machine
  const threadListRuntime = useRemoteThreadListRuntime({
    adapter: threadListAdapter,
    // The runtime for *individual* threads (see next section)
    runtimeHook: useMyChatRuntime, 
  });

  return threadListRuntime;
}

```

> **Warning (Race Condition):** A common issue in custom runtimes is the "First Message Race Condition." When a user sends the *very first* message in a new thread, the thread might not exist in your DB yet.
> `assistant-ui` handles this by waiting for `adapter.initialize()` to return a `remoteId` before it allows the `HistoryAdapter` to save the first message. Ensure your `initialize` function returns the correct ID promptly.

---

## **3. Assistant Transport Runtime**

**Purpose:** Defines how a *single* active thread communicates with the LLM. It manages the "Transport" layer—sending the user's prompt and receiving the stream.

In most implementations, you won't write a raw "TransportRuntime" from scratch. Instead, you use `useLocalRuntime` (which acts as a transport wrapper) or a library-specific hook (like `useVercelUseChatRuntime`).

### **Source Code / Reference Implementation**

This example shows how to build a Transport Runtime that connects to a standard REST API streaming endpoint.

```typescript
import { useLocalRuntime, type ChatModelAdapter } from "@assistant-ui/react";

// 1. Define the Model Adapter (The "Transport" Logic)
const MyModelAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }) {
    // A. Prepare the payload
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
      signal: abortSignal,
    });

    // B. Handle non-streaming errors
    if (!response.ok) throw new Error("Failed to send message");

    // C. Stream the response back to the UI state
    const reader = response.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value, { stream: true });
      // Yielding here updates the `content` state in the UI in real-time
      yield {
        content: [{ type: "text", text: chunk }],
      };
    }
  },
};

// 2. The Runtime Hook
export function useMyChatRuntime() {
  // useLocalRuntime is the standard wrapper for custom transports
  return useLocalRuntime(MyModelAdapter);
}

```

---

## **4. Putting It All Together: Complete Provider**

To use these in your application, you wrap your app in the `AssistantRuntimeProvider`. This provider merges the **Thread List** (DB) and **Transport** (LLM) into a single unified state object.

```tsx
// app/MyAssistant.tsx
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { MyDatabaseRuntime } from "./MyDatabaseRuntime"; // From Section 2

export const MyAssistant = () => {
  // This runtime now possesses both:
  // 1. Knowledge of all your threads (from RemoteThreadListRuntime)
  // 2. Ability to chat (from the runtimeHook passed to it)
  const runtime = MyDatabaseRuntime();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {/* Your UI Components go here */}
      <div className="grid grid-cols-[200px_1fr]">
         <MyThreadSidebar />
         <MyChatWindow />
      </div>
    </AssistantRuntimeProvider>
  );
};

```

### **How this helps State Management**

1. **Optimistic Updates:** When you rename a thread, the Runtime updates the UI immediately, then calls your `adapter.rename` in the background. If the API fails, it can roll back the state.
2. **Context Isolation:** The `AssistantRuntimeProvider` ensures that if you have multiple assistants on one page, their states (messages, loading) do not leak into each other.
3. **Loading States:** The Runtime automatically tracks `isLoading` for both the thread list (fetching history) and the active thread (generating tokens), exposing simple boolean flags to your UI components.

## API for `RemoteThreadListAdapter` 

To implement a fully functional `RemoteThreadListAdapter` for **assistant-ui**, your backend must expose the following set of REST endpoints (or equivalent TRPC/GraphQL mutations).

Here is the concise list of required endpoints:

### 1. List Threads

Retrieves the history of conversations to populate the sidebar.

* **Method:** `GET`
* **Path:** `/api/threads`
* **Request:** None (or pagination query params).
* **Response:** A JSON object containing an array of threads.
```json
{
  "threads": [
    {
      "remoteId": "db_thread_123", // The database primary key
      "title": "React Help",       // Display name
      "createdAt": "2023-10-27T..."
    }
  ]
}

```


* **Frontend Hook:** Maps to `adapter.list()`.

### 2. Create Thread (Initialize)

Creates a new record in your database when the user sends their first message or clicks "New Chat".

* **Method:** `POST`
* **Path:** `/api/threads`
* **Request:**
```json
{
  "localId": "local_temp_id_xyz" // Optional: used to correlate optimistic state
}

```


* **Response:** **(CRITICAL)** Must return the database ID.
```json
{
  "remoteId": "db_thread_456"
}

```


* **Frontend Hook:** Maps to `adapter.initialize()`. The runtime waits for this `remoteId` before saving the first message to the history.

### 3. Rename Thread

Updates the title of a specific thread.

* **Method:** `PATCH` (or `PUT`)
* **Path:** `/api/threads/{threadId}`
* **Request:**
```json
{
  "title": "New Conversation Title"
}

```


* **Response:** `200 OK`.
* **Frontend Hook:** Maps to `adapter.rename()`.

### 4. Delete Thread

Permanently removes a thread.

* **Method:** `DELETE`
* **Path:** `/api/threads/{threadId}`
* **Request:** None.
* **Response:** `200 OK` or `204 No Content`.
* **Frontend Hook:** Maps to `adapter.delete()`.

### 5. Archive / Unarchive Thread (Optional)

Used if your UI supports archiving rather than deleting.

* **Method:** `PATCH`
* **Path:** `/api/threads/{threadId}/archive`
* **Request:**
```json
{
  "archived": true // or false to unarchive
}

```


* **Response:** `200 OK`.
* **Frontend Hook:** Maps to `adapter.archive()` and `adapter.unarchive()`.

---

### **Related Essential Endpoint (History)**

While not part of the `ThreadList` runtime (which only cares about the list), the `Thread` runtime needs this to load the actual chat bubbles when a user clicks a thread from the list.

### 6. Get Thread Messages

* **Method:** `GET`
* **Path:** `/api/threads/{threadId}/messages`
* **Response:** The full conversation history.
```json
{
  "messages": [
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi there!" }
  ]
}

```
