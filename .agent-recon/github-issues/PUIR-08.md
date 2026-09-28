Parent: #22

Priority: P0

## Why

Static `NEXT_PUBLIC_*` values are fixed at build time and the full UI currently
advertises backend features that may not exist. One packaged build needs a
runtime deployment and capability contract.

## Implementation

- Add a same-origin runtime config/capabilities endpoint with a versioned schema.
- Include API base, UI preset, identity mode, enabled features, and tool UI
  capabilities.
- Validate configuration in Python and TypeScript.
- Define loading, unavailable, malformed, and backward-compatible defaults.
- Cache safely while allowing deployment-specific values after wheel build.

## Acceptance Criteria

- One static artifact can start in minimal or full mode without rebuilding.
- Unsupported features are discoverable before their UI mounts.
- Config errors produce a visible recoverable state rather than silent failure.
- Same-origin remains the secure default; external API configuration is tested.
- Schema compatibility tests cover Python and TypeScript consumers.

## Dependencies

- PUIR-02
