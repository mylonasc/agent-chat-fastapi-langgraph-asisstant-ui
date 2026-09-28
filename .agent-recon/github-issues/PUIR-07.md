Parent: #22

Priority: P0

## Why

Existing `/threads` and `/assistant` behavior should remain available while the
new domain and persistence layers become canonical.

## Implementation

- Refactor thread/message routes to call session/transcript services.
- Resolve principals through FastAPI dependencies.
- Preserve current route shapes where safe and document changed insecure
  behavior.
- Auto-create sessions through the service for assistant runs.
- Return consistent JSON errors and status codes.
- Coordinate session deletion with transcript, feedback, and checkpoint ports.

## Acceptance Criteria

- Existing supported clients pass compatibility tests.
- Cross-principal access is rejected.
- No route accesses repository globals directly.
- In-memory and SQLite configurations run the same API contract suite.
- OpenAPI reflects explicit request/response models and errors.

## Dependencies

- PUIR-04
- PUIR-05
- PUIR-06 for persistent checkpoint deletion/context
