# Repository Reconnaissance

This directory is maintainer context: architecture investigations, design
decisions, issue mirrors, and implementation history. It is not the primary
deployment documentation. Start at the [root README](../README.md) for current
usage, then use the reports here when changing architecture.

## Current Architecture Snapshot

- Snapshot refreshed: 2026-09-29
- Package version: `0.5.1`
- Canonical non-RAG runtime: `packages/agent-chat-minimal`
- Portable entry point: `minimal-chat-serve` (single FastAPI/UI server, port
  8011)
- Split development stacks: `docker-compose.minimal.yml` and
  `docker-compose.full.yml`
- Separate RAG demo: `application/backend/full` (source-run, port 8010)

The portable package builds one unified static frontend from
`application/frontend/frontend`, selects its minimal or full layout at runtime
with `UI_PRESET`, and serves it at `/`. `/full/` is no longer a packaged UI
mount. The package's agent registry includes built-ins plus the
`agent_chat.agents` entry-point group; `application/backend/full` intentionally
does not share that registry.

## Current Guides

- [Package and build](package-and-build.md): distribution boundaries, build
  pipeline, runtime and extension points.
- [Root documentation map](../docs/README.md): current user-facing guides.
- [Implementation progress](implementation-progress.md): issue and release
  history. Treat dated status entries as historical records.
- [Decision record and roadmap](decision-record-and-roadmap.md): design
  rationale and planned work. Validate its assumptions against current code
  before acting on an unfinished item.
- [Full backend and persistence](full-backend-and-persistence.md): historical
  investigation of the full RAG backend and persistence design.
- [Frontend contracts](frontend-contracts.md): frontend protocol and design
  investigation.
- [Streaming dependency](streaming-dependency.md): `assistant-stream-ce`
  transport dependency analysis.
- [`github-issues/`](github-issues/): durable copies of PUIR issue bodies.

## Reading Order For Maintainers

1. Read `../docs/README.md` and the relevant user-facing guide.
2. Read [package-and-build.md](package-and-build.md) before changing the
   portable package, wheel, or agent registration.
3. Consult the focused historical reports only for the subsystem being changed.
4. Update this snapshot and the affected report whenever an architectural
   boundary, public command, or deployment mode changes.
