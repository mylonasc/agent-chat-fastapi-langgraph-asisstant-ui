Parent: #22

Priority: P0

## Why

Current thread metadata, UI messages, graph checkpoints, and future feedback
have no shared domain model or ownership boundary. Durable storage must not
cement client-supplied `user_id` as authorization.

## Implementation

- Define `Principal` and injectable `PrincipalResolver` contracts.
- Define session, stored-message, and feedback domain models with UTC
  timestamps, stable IDs, sequence numbers, and metadata.
- Define async repository protocols and application services.
- Implement in-memory adapters first to preserve current test speed/behavior.
- Define deletion, archive, ownership, and feedback-upsert semantics.

## Acceptance Criteria

- Service operations always receive a resolved principal.
- Request body/query `user_id` is not treated as trusted ownership.
- In-memory adapters pass repository contract tests.
- Domain modules import neither FastAPI, LangGraph, nor transport packages.
- Deletion and authorization semantics are documented and tested.

## Dependencies

- PUIR-02
