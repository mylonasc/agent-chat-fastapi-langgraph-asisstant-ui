Parent: #22

Priority: P1

## Why

Feedback is a baseline full-preset requirement but requires stable message
identity, ownership, and durable storage before UI controls are meaningful.

## Implementation

- Add idempotent create/update/get/delete feedback service and routes.
- Support positive/negative rating, optional comment, and metadata.
- Derive actor from the resolved principal.
- Add accessible assistant-message feedback controls and optimistic/retry states.
- Decide whether Assistant UI's feedback adapter is compatible; otherwise use
  the typed client directly behind a local frontend abstraction.

## Acceptance Criteria

- A principal has at most one current feedback record per message.
- Changing or retracting feedback is durable and authorized.
- Feedback survives restart and appears after transcript hydration.
- UI controls are keyboard/screen-reader accessible and expose failures.
- API, repository, and browser tests cover all transitions.

## Dependencies

- PUIR-10
- PUIR-11
