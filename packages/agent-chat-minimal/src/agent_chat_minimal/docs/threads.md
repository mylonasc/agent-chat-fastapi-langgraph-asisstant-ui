# Threads (multi-conversation chats)

The portable server speaks the same thread protocol as the full backend, so
`frontend-full` (thread list, history, multiple chats) works against either
server. Single-prompt clients can ignore this page entirely.

## Concepts

- **Thread**: a conversation id. Metadata (title, owner, archived) is kept by
  the session service (in-memory or SQLite repositories); content lives in
  two places:
  - assistant-ui message objects, stored verbatim per thread as transcript
    payloads (tool UI parts rehydrate on reload);
  - LangGraph checkpointer state keyed by `thread_id` (graph-side memory).
- **Scoped request**: `POST /assistant` accepts `thread_id`/`user_id`
  top-level fields (plus the classic `commands`/`state`). Missing ids are
  auto-generated and their sessions auto-created — the same behavior as the
  full backend.

## Identity

Ownership comes from the resolved principal, never from client-supplied ids.
Send `x-agent-chat-subject: <subject>` to act as that subject; requests
without the header act as `default_user`. Legacy `user_id` query/body fields
are still accepted but must equal the principal — a mismatch is rejected with
403, and `POST /assistant` ignores the body `user_id` entirely. Inject a
custom resolver via `create_app(principal_resolver=...)` for real
authentication (JWT/OAuth/proxy).

## Endpoints

```text
GET    /threads[?user_id=&include_archived=]
POST   /threads                       {localId, user_id?, title?}
GET    /threads/{id}                  PATCH /threads/{id} {title}
POST   /threads/{id}/archive|unarchive
DELETE /threads/{id}                  (also drops transcript, feedback, checkpoints)
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

## Bundled UI presets

The wheel ships one unified frontend at `/` — no separate Next.js server
needed. It is built with `NEXT_PUBLIC_API_BASE=""` so it talks to the same
origin (`/assistant`, `/threads`, `/api/config`). The runtime preset from
`GET /api/config` selects the minimal single-prompt chat or the full thread
sidebar; the legacy `/full/` mount is gone (an explicit `FULL_WEB_DIR`
override still mounts if provided, but no bundle ships for it). To serve a
custom build instead:

```bash
MINIMAL_WEB_DIR=/path/to/frontend/out minimal-chat-serve
```

Pointing an external full frontend at the portable server also works
(`NEXT_PUBLIC_API_URL` without the trailing `/assistant`); thread list,
switching, rename, archive, and history rehydration all use the endpoints
above. Responses stream over the Assistant Stream protocol with
`messages`/`updates`/`custom` events, including `tool_updates` progress
entries like the full backend.

## Persistence notes

- Default storage is in-memory (repositories + `MemorySaver` checkpointer):
  restarts lose it — identical to the full backend's default. Restart-safe
  backends plug in via `create_app(repositories=<SQLiteRepositories>,
  checkpoint_deleter=<checkpoints>)` plus `checkpointer=<saver>` for the
  graph factories (see [persistence.md](persistence.md)).
- Cross-principal access is rejected (403); unknown sessions return 404,
  except `GET .../messages`, which keeps the legacy checkpointer-hydration
  fallback for ids with graph state but no session yet.
- Writing messages to an archived session, or renaming one, returns 409.
  `POST .../messages` for an unknown session returns 404 (orphan writes are
  no longer silently kept).
- AI messages with `tool_calls` but no matching `ToolMessage` are dropped
  before invoke (invalid-history guard, same as full backend).
