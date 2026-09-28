Parent: #22

Priority: P2

## Why

Three backend implementations and stale documents will continue to drift after
the canonical package is improved unless repository applications become thin
composition roots and deprecated surfaces are clearly migrated.

## Implementation

- Convert development minimal/full backends to compose the packaged modules.
- Remove duplicated routing, streaming, thread, and state-reduction code after
  compatibility tests pass.
- Publish route/import/configuration migration guidance and deprecation dates.
- Update root, running, provider, thread, RAG, architecture, and packaging docs.
- Remove dead frontend/backend factories and stale diagrams or regenerate them.
- Close or cross-reference superseded backlog issues.

## Acceptance Criteria

- Canonical behavior is implemented once in the packaged library.
- Development stacks remain useful for contributors without forking behavior.
- Documentation matches shipped presets, capabilities, and persistence.
- Every removed public surface had a documented migration window.
- Architecture diagrams and examples pass their documented smoke paths.

## Dependencies

- PUIR-07
- PUIR-09
- PUIR-14
