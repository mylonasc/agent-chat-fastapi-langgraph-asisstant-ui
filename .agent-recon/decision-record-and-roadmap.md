# UI Refactor Decision Record and Roadmap

## Status

Accepted for the `EPIC_UI-refactor` initiative.

## Product Decisions

- Use an incremental modular rewrite rather than a clean-slate replacement.
- Converge minimal and full frontends into one configurable static application.
- Preserve current routes during a documented deprecation/migration window.
- Default the full preset to sessions, threads/transcripts, and feedback.
- Make RAG, admin, sharing, and attachments optional capabilities rather than
  baseline promises.
- Provide persistent anonymous browser sessions by default and an injectable
  trusted-principal hook for real authentication.
- Keep `assistant-stream-ce` during this initiative, pin it, isolate it behind a
  local transport boundary, and protect it with golden protocol tests.
- Use SQLAlchemy 2.x async repositories with Alembic migrations.
- Persist LangGraph checkpoints in SQLite through a separate adapter and
  lifecycle from session/transcript/feedback repositories.
- Serve validated runtime UI configuration and capabilities from FastAPI.
- Keep the current PyPI distribution during migration and introduce extras for
  optional providers, persistence, and RAG.
- Track work with `[PUIR-NN]` issue title prefixes and an epic checklist.

## Target Architecture

```text
Python distribution
  composition / FastAPI app factory
    runtime settings
    principal resolver
    agent registry
    transport adapter
    session service
    feedback service
    capability provider
  ports
    session repository
    transcript repository
    feedback repository
    graph checkpoint store
  adapters
    in-memory repositories
    SQLAlchemy SQLite repositories
    LangGraph SQLite checkpointer
    assistant-stream-ce transport
  bundled static UI
    one build
    runtime-configured minimal/full preset
    capability-gated features and tools
```

The static frontend remains package data in the wheel. Node/pnpm are release
build dependencies only and never runtime/install dependencies for users.

## Compatibility Policy

- Keep `/assistant`, `/assistant/{agent_id}`, `/threads`, thread mutation routes,
  and `/full` during the migration window.
- Internally map thread routes to the new session service.
- Add canonical versioned/session-oriented routes only when useful; do not
  duplicate APIs without a concrete migration benefit.
- Return explicit JSON 404/501 responses for unsupported API capabilities.
- Emit deprecation documentation before removing imports/routes in a later
  major release.
- Keep the existing distribution name and provide import shims only where a
  released public import would otherwise break.

## Identity Policy

- Anonymous mode assigns a stable opaque subject to the browser.
- A `PrincipalResolver` dependency maps a request to a principal.
- Request bodies do not determine ownership.
- Applications can inject JWT/OAuth/proxy/header identity implementations.
- Anonymous identity is convenience isolation, not authentication.
- Repository/service methods always receive the resolved owner/actor.

## Persistence Policy

- SQLite is the packaged default for one process/node.
- SQLAlchemy repository protocols permit a future PostgreSQL implementation.
- Alembic owns schema upgrades.
- Sessions, messages, and feedback share one transactional application store.
- LangGraph checkpoints use a separate adapter and preferably a separate SQLite
  file or table namespace.
- Stable message IDs and sequence numbers are mandatory before feedback ships.
- Deleting a session cascades transcript and feedback; checkpoint deletion is
  invoked explicitly through its port.

## Delivery Phases

### Phase 0: Stabilize Existing Contracts

- Fix known provider/thread/static-fallback defects.
- Capture the current Assistant Stream wire contract.
- Establish package-level architecture and settings boundaries.

### Phase 1: Backend Foundations

- Add principal/session/transcript/feedback domain contracts.
- Implement SQLAlchemy SQLite repositories and Alembic migrations.
- Add the separate persistent graph checkpoint adapter.
- Refactor current routes onto services while preserving HTTP compatibility.

### Phase 2: Runtime-Configurable UI

- Add runtime configuration and capabilities endpoint.
- Consolidate minimal/full source into one static application.
- Centralize the typed API client and anonymous-session handling.
- Implement stable transcript persistence and reliable hydration.

### Phase 3: Product Features

- Add feedback API and UI.
- Capability-gate optional RAG/admin/share/attachment surfaces.
- Define extension points for specialized tool renderers.

### Phase 4: Packaging and Migration

- Introduce dependency extras and reproducible wheel/sdist builds.
- Install and test final artifacts without Node.
- Convert development backends to package composition roots.
- Publish migration/deprecation documentation and remove stale duplication only
  after compatibility coverage exists.

## Ordered Issues

| ID | Priority | Scope |
|---|---|---|
| PUIR-01 | P0 | Correct baseline package contracts and regressions |
| PUIR-02 | P0 | Introduce modular app/settings/capability boundaries |
| PUIR-03 | P0 | Pin and isolate `assistant-stream-ce`; add golden tests |
| PUIR-04 | P0 | Define principal, session, transcript, and feedback domain ports |
| PUIR-05 | P0 | Add SQLAlchemy SQLite repositories and Alembic migrations |
| PUIR-06 | P1 | Add persistent LangGraph SQLite checkpoint adapter |
| PUIR-07 | P0 | Refactor compatibility routes onto application services |
| PUIR-08 | P0 | Serve runtime UI configuration and capability manifest |
| PUIR-09 | P0 | Consolidate minimal/full into one configurable static frontend |
| PUIR-10 | P0 | Add typed API client and anonymous/auth identity integration |
| PUIR-11 | P0 | Persist stable transcripts and implement reliable hydration |
| PUIR-12 | P1 | Add end-to-end message feedback |
| PUIR-13 | P1 | Capability-gate RAG, admin, sharing, attachments, and tool UIs |
| PUIR-14 | P1 | Harden package extras, static builds, artifact CI, and releases |
| PUIR-15 | P2 | Migrate development apps, docs, and deprecated surfaces |

## Issue Checklist

- [x] #26 PUIR-01: Correct baseline package contracts and regressions
- [ ] #23 PUIR-02: Introduce modular app, settings, and capability boundaries
- [ ] #24 PUIR-03: Pin and isolate `assistant-stream-ce` with protocol tests
- [ ] #27 PUIR-04: Define principal, session, transcript, and feedback domain ports
- [ ] #30 PUIR-05: Add SQLAlchemy SQLite repositories and Alembic migrations
- [ ] #28 PUIR-06: Add persistent LangGraph SQLite checkpoint adapter
- [ ] #29 PUIR-07: Refactor compatibility routes onto application services
- [ ] #25 PUIR-08: Serve runtime UI configuration and capability manifest
- [ ] #35 PUIR-09: Consolidate minimal and full into one configurable static frontend
- [ ] #33 PUIR-10: Add typed frontend API client and identity integration
- [ ] #37 PUIR-11: Persist stable transcripts and implement reliable hydration
- [ ] #31 PUIR-12: Add end-to-end message feedback
- [ ] #36 PUIR-13: Capability-gate optional RAG, admin, sharing, attachments, and tool UIs
- [ ] #32 PUIR-14: Harden package extras, static builds, artifact CI, and releases
- [ ] #34 PUIR-15: Migrate development apps, docs, and deprecated surfaces

## Global Definition of Done

- Installing the wheel does not install or require Node/npm/pnpm.
- One generated static UI supports minimal and full runtime presets.
- Full preset sessions, transcript, feedback, and graph memory survive restart.
- Ownership comes from a principal dependency, never a client-supplied user ID.
- Existing documented HTTP routes work through the migration window.
- Unsupported optional features are hidden and return correct API errors.
- Protocol, repository, migration, browser, and installed-wheel tests run in CI.
- SQLite deployment limits and PostgreSQL extension path are documented.
