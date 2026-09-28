Parent: #22

Priority: P1

## Why

Persisting session metadata without graph memory creates conversations that
appear durable but lose agent context after restart. Checkpoints are a separate
lifecycle and must remain decoupled from application repositories.

## Implementation

- Add a graph checkpoint-store port and LangGraph SQLite adapter.
- Keep checkpoint storage separate from session/transcript/feedback tables or
  use an explicitly isolated namespace.
- Scope checkpoints by session identity and enforce ownership before access.
- Integrate checkpoint deletion with session deletion through the service layer.
- Document single-node SQLite constraints and future PostgreSQL replacement.

## Acceptance Criteria

- Multi-turn graph context survives server restart in the full preset.
- Session deletion applies the documented checkpoint policy.
- Checkpoint implementation can be replaced without changing routes/services.
- Tests cover restart, isolation, deletion, and failure behavior.

## Dependencies

- PUIR-04
- PUIR-05
