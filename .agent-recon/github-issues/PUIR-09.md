Parent: #22

Priority: P0

## Why

Two divergent frontend trees duplicate transport, message conversion, and UI
components. A single runtime-configured static app reduces drift while keeping
Node out of package runtime requirements.

## Implementation

- Align React, Next, Assistant UI, and styling dependency versions.
- Create one application shell consuming runtime config/capabilities.
- Implement minimal and full presets as composition/configuration, not separate
  source trees.
- Consolidate shared transport, converter, primitives, and tool fallback code.
- Preserve `/` and `/full/` entry behavior during migration if required.
- Remove the unused server-only Next API route.

## Acceptance Criteria

- Exactly one frontend source/build is packaged.
- Minimal preset has no thread/admin overhead in the visible experience.
- Full preset exposes configured session features.
- Existing responsive/accessibility checks pass for both presets.
- The generated static app runs from the installed wheel without Node.

## Dependencies

- PUIR-08
- PUIR-03
