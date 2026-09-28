Parent: #22

Priority: P0

## Why

The full packaged baseline needs durable sessions, transcripts, and feedback
without coupling API routes to SQLite details.

## Implementation

- Add SQLAlchemy 2.x async models/repositories for sessions, messages, and
  feedback.
- Use SQLite via `aiosqlite` as the default database implementation.
- Add Alembic migrations and startup/CLI migration behavior.
- Enable foreign keys, WAL, busy timeout, UTC timestamps, indexes, and cascade
  rules.
- Keep repository contracts portable to a future PostgreSQL adapter.
- Add transaction, concurrency, restart, cascade, and migration tests.

## Acceptance Criteria

- Full-preset sessions/messages/feedback survive process restart.
- Migrations work from an empty database and every committed schema revision.
- Repository contract tests pass for memory and SQLite adapters.
- SQLite location and operational constraints are configurable/documented.
- SQLAlchemy is a declared dependency in the appropriate install extra.

## Dependencies

- PUIR-04
