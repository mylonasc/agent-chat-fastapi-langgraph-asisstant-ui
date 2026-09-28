# UI Refactor Implementation Progress

This file is the living handoff for work started from the reconnaissance and
roadmap. The original reports remain a snapshot of revision `cf73417`; this file
records changes made afterward.

## Completed on `main`

| Issue | Commit | Result | Verification |
|---|---|---|---|
| PUIR-01 / #26 | `d120637` | Corrected thread ID resolution, provider-neutral readiness, API SPA exclusions, and agent validation | 35 package tests |
| PUIR-02 / #23 | `077128a` | Added validated settings, composition root, capabilities, static UI boundary, and side-effect-free ASGI factory | 40 package tests |
| PUIR-03 / #24 | `126ff31` | Pinned and isolated `assistant-stream-ce` with golden wire fixtures | 48 package tests |
| PUIR-04 / #27 | `96340f6` | Added principal/session/transcript/feedback domain, ports, services, and memory adapters | 57 package tests |
| PUIR-05 / #30 | `fea9cc5` | Added optional SQLAlchemy SQLite repositories, Alembic migration lifecycle, and artifact resources | 65 package tests plus artifact smoke checks |

The closed issues and epic checklist contain implementation summaries. The
reconnaissance bundle itself was introduced by commit `b91343f`.

## In Review

### PUIR-06 / #28: Persistent LangGraph SQLite checkpoints

Branch: `feature/puir-06-checkpoints`
Draft PR: https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/pull/38

Implemented:

- bounded `langgraph-checkpoint-sqlite` persistence dependency;
- separate checkpoint database settings and documented lifecycle;
- `LangGraphSQLiteCheckpoints` async adapter exposing the official saver;
- official `adelete_thread()` integration through `CheckpointDeleter`;
- restart, multi-turn, isolation, deletion, disposal, and failure-cleanup tests;
- no automatic HTTP composition yet, by design.

PUIR-06 remains open until its draft pull request is reviewed and merged.

## Next Boundary

PUIR-07 should compose the application repositories, checkpoint adapter,
principal resolver, and services into FastAPI lifespan/dependencies, then move
the compatibility `/threads` and `/assistant` routes off process-local globals.
It must preserve current route shapes during the migration window while making
ownership server-derived and deletion semantics explicit.

After PUIR-07, PUIR-08 can safely expose runtime UI configuration and
capabilities from the canonical composition root.

## Test Environment

- Supported verification interpreter used so far: CPython 3.12.3.
- The host's free-threaded CPython 3.14 cannot build the current `orjson`
  dependency; this is an environment/dependency limitation, not a test failure.
- Package-local `uv.lock` files generated during ad hoc runs are intentionally
  removed because this published package does not currently track one.
