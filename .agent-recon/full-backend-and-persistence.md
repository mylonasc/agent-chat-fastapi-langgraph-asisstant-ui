# Full Backend, Sessions, Feedback, and SQLite Reconnaissance

## Current API

The full application is built in
`application/backend/full/fastlang/server/server.py`. Tool routers are included
from a global registry at `server.py:56-60`.

Routes include:

- `GET /health`
- `POST /assistant`
- `GET/POST /threads`
- `GET/PATCH/DELETE /threads/{thread_id}`
- archive/unarchive routes
- `GET/POST /threads/{thread_id}/messages`
- `GET /tools/overview`
- Web RAG routes under `/tools/web_rag`
- Web Search routes under `/tools/web_search`

Web RAG route definitions are in `tools/web_rag/tool.py:184-421` and include
configuration, status, jobs, chunks, raw data, downloads, test search, and a
multiplexed tool POST. Web Search routes are in
`tools/web_search/tool.py:298-327`.

Tool failures often return HTTP 200 with an error object. Configuration,
downloads, status, and jobs are unauthenticated.

## Baseline Agent

The active graph is constructed eagerly at module import
(`server.py:379-397`) using `make_web_rag_search_agent`, model `gpt-4o-mini`,
and `MemorySaver`.

`fastlang/server/get_graph.py:10-45` chooses a ReAct graph by default and a
custom graph when `AGENT_MODE=enforced_rag`. Tools are `web_rag`, `web_search`,
and `web_rag_status`.

The enforced RAG graph likely has an identity/state defect: `RAGState` requires
`user_id` and `thread_id`, while `/assistant` passes only `messages`
(`server.py:462-469`). Thread ID exists in LangGraph config rather than graph
state, and user ID is not injected. ReAct tools fall back to `default_user`
unless the model supplies an argument.

`agent_loader.py` duplicates graph construction but is not used by the running
server. The weather demo is not the active full agent.

## Current Persistence

There is no durable session/thread or feedback database.

Conversation data is divided among:

1. `ThreadManager`, a process-local dictionary guarded by `RLock`
   (`fastlang/server/thread_manager.py:17-72`).
2. `PERSISTED_AUI_MESSAGES`, a global dictionary of arbitrary Assistant UI
   JSON (`server.py:132-135`, `333-376`).
3. LangGraph `MemorySaver`, keyed by only `thread_id`.

Thread metadata contains `id`, `user_id`, `title`, naive `created_at`,
`is_archived`, and `is_public`. It lacks `updated_at`, stable ordering,
agent reference, or concurrency/version metadata.

The message dictionary has no size cap, schema validation, uniqueness,
sequence, transactionality, or durable lifecycle. It can hold messages for a
nonexistent thread. The current frontend does not appear to call the POST
append route, so checkpoint fallback is normally used.

Deleting a thread does not delete the LangGraph checkpoint. Recreating the same
ID can expose old graph state.

RAG artifacts are independently durable using FAISS, JSON/JSONL, and pickle.
The compose file mounts `/app/data` (`docker-compose.full.yml:22-24`), which is
suitable for an SQLite file. SQLAlchemy is present only transitively and is not
a declared direct dependency.

## Feedback Status

Feedback does not exist today:

- no domain model;
- no route;
- no persistence;
- no tests;
- no UI control.

The installed Assistant UI packages contain feedback primitives/adapters, but
the transport runtime type currently exposes only attachment/history adapters.
A direct custom feedback action is the least risky first implementation unless
Assistant UI is upgraded and its adapter contract verified.

## Identity and Authorization

There is no authentication, session middleware, trusted principal, API key,
JWT, OAuth, or ownership dependency. `user_id` is supplied by clients in query
parameters, bodies, and tool arguments.

Consequences:

- callers can claim another user ID and list threads;
- knowing a thread ID permits read/update/archive/delete/message operations;
- checkpoints are globally addressed by thread ID;
- duplicate thread IDs can cross user boundaries;
- RAG user IDs are not security boundaries;
- user IDs influence filesystem paths, creating path-traversal risk in
  `tools/web_rag/vectorstore.py:14-19` and `indexer.py:21-38`.

Persistence should not be marketed as multi-user isolation until identity is
derived from an injected `Principal`, not request bodies.

## Recommended Boundary

Create a subsystem that imports neither LangGraph, agent factories, tool
registry, nor the streaming dependency:

```text
agent_chat/sessions/
  domain.py
  ports.py
  service.py
  router.py
agent_chat/persistence/
  memory.py
  sqlite.py
  migrations/
```

Suggested ports:

```python
class SessionRepository(Protocol):
    async def create(self, session: Session) -> Session: ...
    async def get(self, session_id: str) -> Session | None: ...
    async def list_for_owner(
        self, owner_id: str, include_archived: bool = False
    ) -> list[Session]: ...
    async def rename(
        self, session_id: str, owner_id: str, title: str
    ) -> Session: ...
    async def set_archived(
        self, session_id: str, owner_id: str, archived: bool
    ) -> Session: ...
    async def delete(self, session_id: str, owner_id: str) -> bool: ...

class TranscriptRepository(Protocol):
    async def append(
        self, session_id: str, owner_id: str, message: StoredMessage
    ) -> StoredMessage: ...
    async def list(
        self, session_id: str, owner_id: str
    ) -> list[StoredMessage]: ...

class FeedbackRepository(Protocol):
    async def upsert(self, feedback: Feedback) -> Feedback: ...
    async def get(
        self, session_id: str, message_id: str, actor_id: str
    ) -> Feedback | None: ...
    async def delete(
        self, session_id: str, message_id: str, actor_id: str
    ) -> bool: ...

class AgentConversationPort(Protocol):
    async def stream(self, session_id: str, input: AgentInput): ...
    async def delete_checkpoint(self, session_id: str) -> None: ...
```

The first three are persistence/application concerns. The graph port remains
separate so session and feedback code never depends on a graph implementation.

## Proposed SQLite Schema

### `sessions`

- `id TEXT PRIMARY KEY`
- `owner_id TEXT NOT NULL`
- `title TEXT NOT NULL`
- `status TEXT NOT NULL CHECK(status IN ('active','archived'))`
- `is_public INTEGER NOT NULL DEFAULT 0`
- `agent_ref TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `version INTEGER NOT NULL DEFAULT 1`
- `metadata_json TEXT NOT NULL DEFAULT '{}'`

Index `(owner_id, status, updated_at DESC)`.

### `messages`

- `id TEXT PRIMARY KEY`
- `session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE`
- `sequence_no INTEGER NOT NULL`
- `role TEXT NOT NULL`
- `payload_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `provider_message_id TEXT NULL`
- `run_id TEXT NULL`
- `UNIQUE(session_id, sequence_no)`

Keep the complete Assistant UI object in `payload_json`, but extract identity,
role, ordering, and timestamps into columns.

### `feedback`

- `id TEXT PRIMARY KEY`
- `session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE`
- `message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE`
- `actor_id TEXT NOT NULL`
- `rating TEXT NOT NULL CHECK(rating IN ('positive','negative'))`
- `comment TEXT NULL`
- `metadata_json TEXT NOT NULL DEFAULT '{}'`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `UNIQUE(message_id, actor_id)`

Use idempotent upsert semantics so a changed rating updates one row.

### Migrations

Use a migration ledger or Alembic. A small built-in migration runner is enough
for an initial SQLite-only package, provided upgrades are transactional and
covered by tests.

## API Shape

Preserve `/threads` as compatibility aliases while routing them through a
`SessionService`. New canonical `/sessions` routes can be introduced in a
versioned API later.

Feedback endpoints:

- `PUT /sessions/{session_id}/messages/{message_id}/feedback`
- `GET /sessions/{session_id}/messages/{message_id}/feedback`
- `DELETE /sessions/{session_id}/messages/{message_id}/feedback`

The actor comes from `Principal.subject`, never request JSON.

Example request:

```json
{
  "rating": "positive",
  "comment": null,
  "metadata": {}
}
```

## SQLite Operational Defaults

- Declare `aiosqlite` directly, or `sqlalchemy[asyncio]` plus `aiosqlite`.
- Enable foreign keys.
- Use WAL journal mode and a busy timeout.
- Keep write transactions short.
- Store UTC timestamps.
- Default path: `/app/data/agent-chat.sqlite3` or a platform-appropriate user
  data directory.
- Treat SQLite as a single-node/small deployment default, not a shared
  multi-replica database.
- Keep graph checkpoint persistence in a separate adapter/file or clearly
  separate schema; session persistence alone does not persist agent memory.

## Message Identity Requirement

The frontend currently overwrites message IDs with array indexes. Feedback
cannot safely target those IDs. Before enabling feedback:

- preserve or generate UUID message IDs at creation;
- retain IDs through stream conversion and hydration;
- assign stable sequence numbers;
- define whether feedback applies to the assistant envelope or individual tool
  parts;
- backfill legacy messages deterministically only if migration is required.

## Migration Path

1. Add domain DTOs, protocols, and `SessionService`.
2. Implement in-memory adapters preserving current behavior.
3. Refactor routes to use interfaces and ownership policy.
4. Add SQLite repositories and migration lifecycle.
5. Optionally dual-write during one compatibility release.
6. Export live in-memory data only if preservation across rollout matters.
7. Switch reads to SQLite and remove globals.
8. Add feedback routes and UI after stable message IDs.
9. Separately choose a persistent LangGraph SQLite checkpointer.

Current in-memory state cannot be migrated after process restart. RAG files do
not require migration.

## Deletion Semantics to Define

Session deletion must explicitly decide the fate of:

- UI transcript;
- feedback;
- graph checkpoint;
- RAG artifacts;
- analytics/audit records.

SQLite cascade can remove transcript/feedback. Graph checkpoint deletion must
go through `AgentConversationPort`; RAG data should remain independent unless a
product-level delete-all-user-data operation is invoked.

## Risks and Missing Tests

High risks:

- no trusted identity or ownership enforcement;
- stable feedback targets do not exist;
- durable sessions can diverge from in-memory checkpoints;
- current frontend does not populate the UI message store;
- enforced RAG identity is not propagated;
- client-controlled RAG paths;
- multiple workers have isolated process state today.

Tests needed:

- ownership violations and duplicate IDs across owners;
- persistence across app restart;
- concurrent writes, lock timeout, and rollback;
- migration from every released schema;
- foreign-key cascades;
- feedback create/update/retract;
- stable IDs through stream and hydration;
- graph checkpoint deletion policy;
- enforced RAG principal propagation;
- path traversal rejection;
- multi-worker behavior/documented constraints.
