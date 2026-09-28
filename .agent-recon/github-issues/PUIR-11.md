Parent: #22

Priority: P0

## Why

The backend message append route is not wired, hydration relies on unstable
internal APIs, and index-derived IDs cannot support durable feedback.

## Implementation

- Generate and preserve stable message IDs through commands, stream state,
  database rows, conversion, and hydration.
- Persist complete Assistant UI message payloads with extracted role, sequence,
  run/provider IDs, and timestamps.
- Integrate the supported history adapter or a repository-owned equivalent.
- Make hydration race-safe across thread changes and cancellation.
- Define tool-call/tool-result persistence and transcript/checkpoint precedence.

## Acceptance Criteria

- Rich tool messages render equivalently after reload.
- IDs remain stable when messages are inserted, branched, or rehydrated.
- Concurrent append ordering is deterministic and constrained in the database.
- Thread switching cannot hydrate data into the wrong runtime.
- Restart and browser E2E tests cover multi-turn transcripts.

## Dependencies

- PUIR-05
- PUIR-07
- PUIR-09
- PUIR-10
