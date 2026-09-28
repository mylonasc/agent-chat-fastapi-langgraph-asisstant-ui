Parent: #22

Priority: P1

## Why

The hard packaging requirement is that users install and run without Node. The
release workflow currently tests source before build and only shallowly inspects
the final archives.

## Implementation

- Keep the current distribution name and add explicit provider, persistence,
  and RAG extras.
- Use one reproducible frontend build/staging command locally and in CI.
- Build wheel and sdist, then install/test each in clean environments without
  Node on `PATH`.
- Exercise minimal/full presets, runtime config, docs, entry points, static
  assets, offline fake streaming, SQLite migrations, and restart persistence.
- Derive one package version source and strengthen release tag checks.
- Test all supported Python versions.

## Acceptance Criteria

- Installed artifacts require no Node/npm/pnpm dependency or executable.
- CI tests the exact artifacts uploaded to PyPI.
- Wheel and sdist contain the complete static app and runtime resources.
- Optional extras install independently and have documented dependency bounds.
- Local and CI release paths cannot drift.

## Dependencies

- PUIR-05
- PUIR-09
- PUIR-13
