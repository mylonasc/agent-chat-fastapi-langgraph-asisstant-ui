# Repository Reconnaissance

This directory captures the architecture exploration performed for the packaged
minimal and full agent-chat library. It is intended as durable context for
design and implementation work.

## Snapshot

- Repository revision inspected: `cf73417`
- Package version inspected: `0.3.5`
- Inspection date: 2026-09-28
- Scope: packaged Python library, bundled minimal/full UIs, full FastAPI
  backend, persistence/session/feedback design, and `assistant-stream-ce`
- No application code was changed during reconnaissance.

## Reports

- [package-and-build.md](package-and-build.md): Python package, public API,
  bundled assets, publishing, existing tests, and package/repository drift.
- [full-backend-and-persistence.md](full-backend-and-persistence.md): full API,
  agent construction, current persistence, identity/security assumptions, and
  an SQLite session/feedback boundary.
- [frontend-contracts.md](frontend-contracts.md): minimal/full runtime
  architecture, static-export configuration, thread/history behavior, admin,
  tools, feedback, and frontend consolidation options.
- [streaming-dependency.md](streaming-dependency.md): exact
  `assistant-stream-ce` responsibilities, protocol coupling, version risk, and
  retain/isolate/replace options.
- [decision-record-and-roadmap.md](decision-record-and-roadmap.md): accepted
  product decisions, target architecture, phased roadmap, and issue checklist.
- [implementation-progress.md](implementation-progress.md): living status,
  shipped commits, verification results, and the next implementation boundary.
- [`github-issues/`](github-issues/): durable copies of every PUIR issue body.

## GitHub Issues

- [EPIC_UI-refactor #22](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/22)
- [PUIR-01 #26](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/26): baseline contracts and regressions
- [PUIR-02 #23](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/23): modular app/settings/capability boundaries
- [PUIR-03 #24](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/24): stream dependency isolation
- [PUIR-04 #27](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/27): identity and persistence domain ports
- [PUIR-05 #30](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/30): SQLAlchemy SQLite and Alembic
- [PUIR-06 #28](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/28): persistent graph checkpoints
- [PUIR-07 #29](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/29): compatibility routes and services
- [PUIR-08 #25](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/25): runtime UI configuration
- [PUIR-09 #35](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/35): unified static frontend
- [PUIR-10 #33](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/33): typed API client and identity
- [PUIR-11 #37](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/37): durable transcript and hydration
- [PUIR-12 #31](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/31): message feedback
- [PUIR-13 #36](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/36): optional capability gating
- [PUIR-14 #32](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/32): packaging and artifact CI
- [PUIR-15 #34](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/34): app and documentation migration

## Cross-Cutting Conclusions

1. The portable wheel concept is sound: Node is required only while producing
   release artifacts, not when installing or running the wheel.
2. The package currently combines reusable backend concerns, demo agents,
   in-memory persistence, and two static applications in one large server
   module. These need explicit boundaries before adding more features.
3. The bundled full UI is not fully compatible with the packaged backend. It
   exposes RAG/admin capabilities whose `/tools/*` routes only exist in the
   separate full backend.
4. Runtime configurability is limited because `NEXT_PUBLIC_*` values are baked
   into static assets. A same-origin runtime configuration endpoint/file and a
   capability manifest are the highest-leverage frontend improvements.
5. Session metadata, UI transcripts, LangGraph checkpoints, and future
   feedback are separate persistence concerns. They should be connected by
   service interfaces, not merged into agent/stream code.
6. SQLite is a sensible default for a single-process packaged deployment. It
   should be one repository implementation behind storage protocols so a
   PostgreSQL implementation can be added without changing routes or agents.
7. Identity is currently client-supplied (`default_user`) and is not an
   authorization boundary. Persisting this behavior would make insecure access
   durable; introduce a `Principal` abstraction before promising multi-user
   isolation.
8. `assistant-stream-ce` should not be replaced immediately. Pin it, isolate it
   behind a repository-owned transport adapter, and add golden protocol tests.
   Reconsider replacement after the package contracts are stable.
9. The repository has three drifting backend implementations. The packaged
   application should become the canonical implementation, with development
   applications reduced to thin composition roots.
10. A full rewrite is possible but not necessary as a first move. An
    incremental modularization can retain the working protocol and wheel while
    replacing storage, configuration, and composition boundaries independently.

## Immediate Priorities Found During Reconnaissance

- Use `resolve_thread_id()` in the real assistant route; documented
  `runConfig.thread_id` is currently ignored there.
- Remove model-agnostic `OPENAI_API_KEY` gating so Ollama/Anthropic models work
  as documented.
- Prevent `/tools/*` requests from falling through to SPA HTML.
- Hide or capability-gate full UI admin/RAG features when unsupported.
- Establish stable message IDs before adding message feedback.
- Wire durable transcript persistence or explicitly remove the unused message
  append contract.
- Run the final built wheel smoke test in release CI, including `/full/`.
- Consolidate settings; current `Settings` is not the actual source of truth.
- Replace hard-coded `default_user` with an injected identity/session policy.
- Make thread deletion semantics cover transcript, feedback, and optionally
  graph checkpoints through separate ports.

## Suggested Design Direction

Keep one distribution initially, but internally separate it into:

```text
agent_chat/
  app.py                 # FastAPI composition
  config.py              # validated runtime settings
  agents/                # registry and graph ports
  transport/             # assistant protocol adapter
  sessions/              # domain, services, repository protocols
  persistence/
    memory.py
    sqlite.py
    migrations/
  feedback/              # DTOs/service/routes or sessions subdomain
  ui/                    # static mounts, runtime config, capabilities
  demo/                  # optional reference agents
```

The static UI stays inside the wheel. Build-time frontend tooling remains a
maintainer/release concern and is not a package runtime dependency.
