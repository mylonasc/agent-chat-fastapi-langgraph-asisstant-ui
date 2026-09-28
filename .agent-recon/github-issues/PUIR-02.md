Parent: #22

Priority: P0

## Why

The package currently concentrates app composition, routes, transport,
persistence defaults, static serving, and CLI behavior in one module. Explicit
boundaries are required before storage and frontend behavior can evolve safely.

## Implementation

- Introduce a validated application settings model passed to `create_app()`.
- Split composition, API routers, static UI mounting, agents, and infrastructure
  wiring into focused modules.
- Define a capability provider used by both routes and runtime UI config.
- Remove import-time construction side effects from reusable modules while
  retaining a documented ASGI entry point.
- Preserve released top-level imports through the migration window.

## Acceptance Criteria

- `create_app()` has one explicit configuration source.
- Importing reusable modules does not construct graphs or open databases.
- Existing routes and supported public imports continue to work.
- Minimal and full presets can be assembled from the same composition root.
- Architecture boundaries are covered by app-factory tests.

## Dependencies

- PUIR-01
