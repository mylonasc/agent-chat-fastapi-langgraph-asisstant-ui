# assistant-ui multi-thread history & “element hydration” reference

This note is a **practical reference** for implementing and debugging **multi-thread chat history** in **assistant-ui** using **ThreadList** + a custom backend (including an *assistant transport* backend).

It focuses on the **recommended architecture**:

- **Thread metadata** (id/title/archived) comes from a **RemoteThreadListAdapter**
- **Per-thread messages** (including “elements” like tool UI parts) come from a **ThreadHistoryAdapter**
- The **history adapter is injected per thread** via the adapter’s `unstable_Provider` + `RuntimeAdapterProvider`

---

## Why “hydrating elements” is tricky

assistant-ui messages are not just `{ role, text }`.

A message can contain multiple **parts** (text, tool-call, tool-result, attachments, UI parts, etc.). If you only persist “plain text”, then on reload:

- tool calls/results may not render
- custom Tool UI may not render
- attachments/other parts won’t re-hydrate

**Rule of thumb:** persist **the entire message object** you receive in `history.append(message)`, and return it exactly (or semantically equivalent) from `history.load()`.

---

## The moving pieces (what goes where)

### 1) RemoteThreadListAdapter (thread metadata only)

Responsibilities:

- `list()` → returns an array of threads (remoteId, title, status, etc.)
- `initialize(localId)` → create a server-side thread record and return `remoteId`
- `rename(remoteId, title)`
- `archive(remoteId)` / `unarchive(remoteId)`
- `delete(remoteId)`
- optional `generateTitle(...)` (returns an AssistantStream)

> **Important:** `list()` hydrates the **thread list**, **not** messages.

### 2) runtimeHook (per-thread runtime creation)

In a multi-thread UI, each open thread gets a fresh runtime instance from:

- `useAssistantTransportRuntime(...)` (if you’re using assistant transport)
- or `useLocalRuntime(modelAdapter)`
- or other supported hooks

This runtime is what streams and renders the live conversation.

### 3) ThreadHistoryAdapter (message persistence & rehydration)

Responsibilities per thread:

- `load()` → fetch persisted messages for the **current thread** and return `{ messages }`
- `append(message)` → persist each new message (user + assistant + tool parts)
- optional `resume({ messages })` → resume an interrupted run if your backend supports it

### 4) `unstable_Provider` (where thread-specific adapters are injected)

In multi-thread mode, **you must inject history per thread**, because you need access to the thread’s `remoteId`.

This is why assistant-ui recommends the `unstable_Provider` pattern.

---

## Lifecycle cheatsheet (multi-thread)

### Page load
1. `useRemoteThreadListRuntime` calls `adapter.list()`
2. UI shows the list of threads (titles, archived state, etc.)

### User opens a thread
1. runtime is spawned via your `runtimeHook`
2. your injected `history.load()` is called
3. returned messages are rendered (including tool-call UI, etc.)

### User sends the *first* message in a new thread
1. UI creates a local thread id
2. on first send, `adapter.initialize(localId)` is called
3. you now have a canonical `remoteId`
4. **history.append may be called very early** → you must avoid race conditions

---

## The most common bug: race condition on the first message

**Symptom:** first message is not persisted, or is persisted into a wrong thread, or thread switch errors appear.

**Cause:** `history.append(message)` can run **before** the thread is fully initialized.

**Fix:** in `append`, always do:

```ts
const { remoteId } = await api.threadListItem().initialize(); // safe to call multiple times
```

Then persist using `remoteId`.

---

## Suggested implementation pattern (TypeScript)

Below is a compact but realistic pattern for:

- thread list adapter
- per-thread history adapter injected through `unstable_Provider`
- assistant transport runtime per thread

> The exact imports/types can vary slightly across versions, but the architecture remains the same.

### 1) ThreadList provider wiring

```tsx
"use client";

import React, { useMemo } from "react";
import {
  AssistantRuntimeProvider,
  RuntimeAdapterProvider,
  unstable_useRemoteThreadListRuntime as useRemoteThreadListRuntime,
  type unstable_RemoteThreadListAdapter as RemoteThreadListAdapter,
} from "@assistant-ui/react";

import { useAssistantTransportRuntime } from "@assistant-ui/react-ai-sdk";
import { useAssistantApi, type ThreadHistoryAdapter } from "@assistant-ui/react";

function useMyPerThreadRuntime() {
  // This hook must create a *fresh* runtime instance per thread.
  // If using assistant transport, you typically pass a transport config here.
  // Example shape (pseudo):
  return useAssistantTransportRuntime({
    // api: "/api/assistant-transport",
    // headers/body that your backend expects
  });
}

export function CustomThreadListProvider({ children }: { children: React.ReactNode }) {
  const threadListAdapter: RemoteThreadListAdapter = useMemo(
    () => ({
      async list() {
        const res = await fetch("/api/threads");
        const threads = await res.json();

        return {
          threads: threads.map((t: any) => ({
            remoteId: t.id,
            title: t.title ?? undefined,
            status: t.archived ? "archived" : "regular",
            externalId: t.externalId ?? undefined,
          })),
        };
      },

      async initialize(localId) {
        const res = await fetch("/api/threads", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ localId }),
        });
        const t = await res.json();
        return { remoteId: t.id, externalId: t.externalId ?? undefined };
      },

      async rename(remoteId, title) {
        await fetch(`/api/threads/${remoteId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title }),
        });
      },

      async archive(remoteId) {
        await fetch(`/api/threads/${remoteId}/archive`, { method: "POST" });
      },

      async unarchive(remoteId) {
        await fetch(`/api/threads/${remoteId}/unarchive`, { method: "POST" });
      },

      async delete(remoteId) {
        await fetch(`/api/threads/${remoteId}`, { method: "DELETE" });
      },

      // Optional: generateTitle(remoteId) => AssistantStream
    }),
    []
  );

  const runtime = useRemoteThreadListRuntime({
    runtimeHook: useMyPerThreadRuntime,
    adapter: {
      ...threadListAdapter,

      // The key: inject per-thread adapters here.
      unstable_Provider: ({ children }) => {
        const api = useAssistantApi();

        const history: ThreadHistoryAdapter = useMemo(
          () => ({
            async load() {
              // The remoteId is available once a thread is initialized or selected.
              // If your backend needs remoteId explicitly, read it via api/thread item
              // patterns (see below).
              const { remoteId } = await api.threadListItem().initialize();

              const res = await fetch(`/api/threads/${remoteId}/messages`);
              const { messages } = await res.json();

              return { messages };
            },

            async append(message) {
              // Fix race condition on first message:
              const { remoteId } = await api.threadListItem().initialize();

              await fetch(`/api/threads/${remoteId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message }),
              });
            },

            // Optional: resume({ messages }) { ... }
          }),
          [api]
        );

        return (
          <RuntimeAdapterProvider adapters={{ history }}>
            {children}
          </RuntimeAdapterProvider>
        );
      },
    },
  });

  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}
```

### Notes on the example

- `unstable_Provider` runs **inside each thread context**, so `useAssistantApi()` works.
- `history.load()` is called when the thread is opened (or otherwise needs to show history).
- `history.append()` is called for every message; always `await initialize()` to avoid race conditions.
- The message you persist should be stored as JSON and returned unchanged.

---

## Backend API shape (suggested)

### `GET /api/threads`
Returns metadata only:

```json
[
  { "id": "th_123", "title": "Debug session", "archived": false }
]
```

### `POST /api/threads`
Creates a thread:

```json
{ "localId": "local_abc" }
```

Returns:

```json
{ "id": "th_123", "externalId": "customer_789" }
```

### `GET /api/threads/:id/messages`
Returns:

```json
{
  "messages": [
    { "id": "...", "role": "user", "content": [/* parts */] },
    { "id": "...", "role": "assistant", "content": [/* parts */] }
  ]
}
```

### `POST /api/threads/:id/messages`
Accepts:

```json
{ "message": { "role": "assistant", "content": [/* parts */] } }
```

Store `message` as JSON.

---

## “Hydrating elements”: what to store

### You want to store:
- the **message role**
- the **content parts array** (text parts, tool-call parts, tool-result parts, attachment parts, etc.)
- any message-level metadata that assistant-ui uses to render and reconcile messages

### You do NOT want to store only:
- `text`
- or a “flattened” representation

If you do, tool calls/results cannot be reconstructed and your Tool UI won’t reappear.

---

## Debugging checklist (fast)

### Thread list works, but history doesn’t show
- Does your `history.load()` run? Put a server log + browser log.
- Are you returning `{ messages }` with the correct shape?
- Are you storing the *full message objects* from `append()`?

### First message missing or saved to wrong thread
- In `append()`, are you awaiting `api.threadListItem().initialize()`?
- Are you using `remoteId` returned from that call?

### Switching threads throws errors like “Cannot read properties of undefined (reading 'id')”
Common causes:
- `load()` returns messages missing expected fields (ids/parts)
- mixing manual “import” calls with history adapter loading
- returning `undefined` instead of `{ messages: [] }` for empty threads

### Tool UI parts show live, but disappear on reload
- You persisted only final assistant text, not tool-call/tool-result parts
- Or your backend “collapses” messages and drops parts
- Or your tool results are not being persisted (sometimes tool-result parts are emitted separately)

> Tip: temporarily log the exact message object passed to `append(message)` and compare it to what you return from `load()`.

---

## Recommended “known-good” reading order (docs)

(Official docs pages that are most relevant.)

```text
Custom Thread List:
https://www.assistant-ui.com/docs/runtimes/custom/custom-thread-list

LocalRuntime & History Adapter:
https://www.assistant-ui.com/docs/runtimes/custom/local

Tool UI (generative UI elements):
https://www.assistant-ui.com/docs/guides/ToolUI

AI SDK integration reference:
https://www.assistant-ui.com/docs/api-reference/integrations/vercel-ai-sdk
```

---

## Refactoring tips

- Keep “thread list” and “thread history” separate.
- Prefer adapter-driven hydration (`history.load`) over manual runtime imports.
- Store messages verbatim as JSON; treat any “normalization” as risky until you have tests.
- Add a small “history roundtrip test”:
  1) send a message that triggers a tool call
  2) confirm Tool UI renders
  3) reload the page
  4) confirm Tool UI rehydrates

---

## Appendix: minimal database schema example

```ts
interface ThreadRecord {
  id: string;        // remoteId
  title?: string;
  archived: boolean;
  createdAt: string;
  updatedAt: string;
}

interface MessageRecord {
  id: string;        // you can generate server-side
  threadId: string;  // remoteId
  createdAt: string;
  message: unknown;  // the full assistant-ui message JSON
}
```

---

## Appendix: common anti-patterns

### ❌ Persisting only plain text
```ts
await db.save({ role: message.role, text: extractText(message) }); // loses parts
```

### ❌ Hydrating by manually “importing” messages into a thread runtime (multi-thread)
This often breaks switching, ids, and element rehydration when combined with ThreadList.
Prefer `history.load()`.

### ❌ Checking `if (!remoteId)` instead of awaiting initialization
This is a race condition magnet. Always await initialize.

---

## Quick “what to log” when it fails

- `initialize()` result (remoteId)
- the exact `message` object received by `append(message)`
- the exact JSON returned from `/messages` in `load()`
- the order of calls when switching threads (load → append → load, etc.)

That’s usually enough to spot shape mismatches and race conditions quickly.
