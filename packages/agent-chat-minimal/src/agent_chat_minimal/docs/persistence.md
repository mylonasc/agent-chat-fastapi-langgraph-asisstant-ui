# Persistence Domain

The canonical package separates chat persistence into four framework-independent
layers: dataclass models in `domain`, async protocols in `ports`, authorization
and lifecycle rules in `services`, and implementations in `adapters`. These
modules do not depend on FastAPI, LangGraph, assistant-stream, or SQLAlchemy.
Existing HTTP routes and legacy thread stores remain unchanged until PUIR-07.

Every service call receives a trusted `Principal`. Ownership is always derived
from `Principal.subject`; a `user_id` supplied by a request body or query is
never an authorization input. A missing entity raises `NotFoundError`, an
entity belonging to another principal raises `ForbiddenError`, and duplicate,
archived-mutation, or concurrent-change conditions raise `ConflictError`.

Sessions have stable IDs, aware UTC timestamps, and explicit `active` or
`archived` status. Archiving is reversible and preserves transcripts and
feedback. Archived sessions remain readable but cannot be renamed or receive
new messages or feedback. Messages have stable IDs and a positive,
session-local sequence. Their payload is transport-neutral so an adapter can
persist complete UI message data without importing a UI protocol.

There is at most one feedback record per `(session_id, message_id)`. Upsert
preserves its ID and creation timestamp; submitting the same rating, optional
comment, and metadata again returns the existing record unchanged. Ratings are
`positive` or `negative`.

`SessionService.delete` verifies ownership, invokes an optional
`CheckpointDeleter`, then removes feedback, transcript entries, and session
metadata. The service currently
calls multiple repository methods and is therefore not a cross-repository unit
of work. PUIR-07 composition should delete through the SQL session repository,
whose database foreign keys atomically cascade to messages and feedback. It
must not claim that the existing application-service sequence is atomic.

`InMemoryRepositories` supplies reference adapters for composition and fast
tests. New repository adapters should run the reusable repository contract tests
before being connected to the services.

## SQLite adapter

Install the optional dependencies with:

```bash
pip install "agent-chat-fastapi-langgraph-assistant-ui[persistence]"
```

Open one shared bundle and dispose it explicitly during application shutdown:

```python
from agent_chat_minimal.adapters.sqlite import SQLiteRepositories, sqlite_url

repositories = await SQLiteRepositories.open(sqlite_url("./agent-chat.db"))
try:
    session = await repositories.sessions.get("session-id")
finally:
    await repositories.dispose()
```

`SQLiteRepositories.open(..., migrate=True)` upgrades to the packaged Alembic
head before returning. Set `migrate=False` when deployment tooling performs
migrations separately. `upgrade_database(engine)` and
`current_database_revision(engine)` are the programmatic migration lifecycle;
`minimal-chat-migrate PATH` is the corresponding command. Migration resources
ship in both wheel and sdist.

Each connection enables `foreign_keys`, WAL journal mode, and a 5000 ms busy
timeout. The schema stores metadata and message payloads as JSON, stores UTC
timestamps as ISO-8601 text so loaded domain values remain UTC-aware, and
enforces stable primary keys, one sequence per session, one feedback row per
message, parent consistency, indexes, and foreign-key cascades.

SQLite is intended for one application process/node. WAL improves local reader
and writer coexistence but does not turn a SQLite file into a multi-node store.
Keep the database and its WAL files on local durable storage, ensure the parent
directory already exists and is writable, and use a future repository adapter
for PostgreSQL deployments.

## LangGraph checkpoints

Graph state uses the maintained `langgraph-checkpoint-sqlite` package through a
separate adapter and SQLite file:

```python
from agent_chat_minimal.adapters.langgraph_sqlite import LangGraphSQLiteCheckpoints

checkpoints = await LangGraphSQLiteCheckpoints.open(
    settings.resolved_checkpoint_database_url()
)
try:
    app = create_app(checkpointer=checkpoints.checkpointer)
finally:
    await checkpoints.dispose()
```

Opening eagerly runs `AsyncSqliteSaver.setup()`; disposal closes its async
connection. Session IDs are used unchanged as LangGraph `thread_id` values.
Routes and services must validate the session and enforce ownership before graph
access or `delete_session`; the raw saver contains no user identity policy.
Deletion uses the saver's official `adelete_thread()` API and removes every
checkpoint namespace and pending write for that session.

Keep `CHECKPOINT_DATABASE_PATH`/`CHECKPOINT_DATABASE_URL` distinct from the
application `DATABASE_PATH`/`DATABASE_URL`. SQLite checkpointing is suitable for
one process/node on local durable storage. A future PostgreSQL checkpointer can
replace this adapter without changing service or route contracts.
