Parent: #22

Priority: P0

## Why

API base logic, error handling, and `default_user` are duplicated and unsafe.
The unified frontend needs one typed client and an explicit anonymous/auth
identity lifecycle.

## Implementation

- Add a typed API client using runtime configuration.
- Centralize status/error parsing, cancellation, credentials, and base paths.
- Generate/store an opaque anonymous browser session identity for the default
  mode and exchange it through the backend identity mechanism.
- Support an injected authenticated mode without embedding auth policy in UI
  components.
- Remove hard-coded `default_user` and direct component fetches.

## Acceptance Criteria

- All application requests use the typed client.
- Anonymous sessions are stable across reloads and isolated in tests.
- Authenticated principal integration has a documented extension contract.
- Network and malformed-response failures are visible and recoverable.
- No UI component treats tool args or body `user_id` as trusted identity.

## Dependencies

- PUIR-04
- PUIR-07
- PUIR-08
- PUIR-09
