# Threads (multi-conversation chats)

The portable server speaks the same thread protocol as the full backend, so
`frontend-full` (thread list, history, multiple chats) works against either
server. Single-prompt clients can ignore this page entirely.

## Concepts

- **Thread**: a conversation id. Metadata (title, owner, archived) is kept by
  `ThreadManager`; content lives in two places:
  - assistant-ui message objects, stored verbatim per thread (tool UI parts
    rehydrate on reload);
  - LangGraph checkpointer state keyed by `thread_id` (graph-side memory).
- **Scoped request**: `POST /assistant` accepts `thread_id`/`user_id`
  top-level fields (plus the classic `commands`/`state`). Missing ids are
  auto-generated and their metadata auto-created — the same behavior as the
  full backend.

## Endpoints

```text
GET    /threads[?user_id=&include_archived=]
POST   /threads                       {localId, user_id?, title?}
GET    /threads/{id}                  PATCH /threads/{id} {title}
POST   /threads/{id}/archive|unarchive
DELETE /threads/{id}                  (also drops stored messages)
GET    /threads/{id}/messages         (persisted UI messages, else checkpointer fallback)
POST   /threads/{id}/messages         {message}  (history.append hook)
POST   /assistant  POST /assistant/{agent_id}    (scoped shape supported)
```

## Example flow

```bash
curl -X POST localhost:8011/threads -H 'Content-Type: application/json' \
  -d '{"localId":"trip","title":"Trip planning"}'

curl -X POST localhost:8011/assistant -H 'Content-Type: application/json' \
  -d '{"thread_id":"trip","state":{"thread_id":"trip"},"commands":[]}'

curl localhost:8011/threads/trip/messages
```

## Frontend-full compatibility

Point the full frontend at the portable server (`NEXT_PUBLIC_API_URL` without
the trailing `/assistant`); thread list, switching, rename, archive, and
history rehydration all use the endpoints above. Responses stream over the
Assistant Stream protocol with `messages`/`updates`/`custom` events, including
`tool_updates` progress entries like the full backend.

## Persistence notes

- Default storage is in-memory (`MemorySaver` + dicts): restarts lose it —
  identical to the full backend's default. Restart-safe backends plug in via
  `create_app(checkpointer=<saver>)`.
- History larger than the 500-message store cap (or 200 tool updates) is
  trimmed oldest-first.
- AI messages with `tool_calls` but no matching `ToolMessage` are dropped
  before invoke (invalid-history guard, same as full backend).
