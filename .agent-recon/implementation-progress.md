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

## In Progress (same branch, per maintainer direction)

### PUIR-07 / #29: Compatibility routes onto application services

Implemented on `feature/puir-06-checkpoints` (no new branch):

- new `identity.py`: `DefaultPrincipalResolver` (`x-agent-chat-subject`
  header, `default_user` fallback); injectable via
  `create_app(principal_resolver=...)`;
- `server.py` routes call `SessionService`/`TranscriptService`; no route
  touches repository state. `thread_manager`/`message_store` kwargs are
  deprecated best-effort-migrated shims;
- ownership is server-derived: legacy `user_id` query/body must equal the
  principal (403 on mismatch); `POST /assistant` ignores body `user_id` and
  auto-creates owned sessions; deletion cascades transcript/feedback plus the
  `checkpoint_deleter` port;
- `CreateThreadBody.user_id` is now optional (`None` = no legacy claim) so
  header-identified clients can omit it;
- `composition.py` passes through `repositories`/`session_service`/
  `transcript_service`/`principal_resolver`/`checkpoint_deleter`; defaults
  stay in-memory (no file side effects);
- new `tests/test_compatibility_contract.py` runs the same CRUD, isolation
  (403), cascade, auto-create, archived-409, and OpenAPI assertions against
  in-memory and SQLite backends;
- docs updated: `threads.md` (identity + behavior changes), `persistence.md`
  (composition), `configuration.md` (new hooks + SQLite/checkpoint example).

Verification: 87 package tests pass (71 pre-existing + 16 contract).

Maintainer manual test (full UI against packaged app): thread CRUD, messages,
archive, and assistant runs work. The full UI polls
`GET /tools/web_rag/status` (every ~1.2 s) and receives a refusal. This is
the known, documented incompatibility (recon conclusion #3; RAG routes live
only in the separate full backend, gating is PUIR-13): the frontend checks
`!res.ok` and degrades gracefully, and the backend answers JSON rather than
SPA HTML (PUIR-01 exclusion holds). Hardened further with an explicit
`501 {"detail": {"error": "capability_disabled", ...}}` refusal for
`/tools/*` so "unsupported here" is distinguishable from a mistyped URL.

UI staging: `web/`/`web_full/` are gitignored build outputs, so a source
checkout starts API-only. `scripts/stage_ui.sh` rebuilds and stages both
exports (verified `/` and `/full/` served with API intact); `RUNNING.md`
documents it and the wheel smoke test now asserts `/full/` too.

## Next Boundary

PUIR-07 composition is implemented (above) and awaits maintainer manual
testing, then merge of the draft PR.

After PUIR-07 merges, PUIR-08 can safely expose runtime UI configuration and
capabilities from the canonical composition root.

## In Progress

### PUIR-08 / #25: Runtime UI configuration and capability manifest

Branch: `feature/puir-08-runtime-config`

Implemented (backend-first slice; component wiring stays PUIR-09/PUIR-13):

- `Settings.api_base` (`API_BASE`, same-origin `""` default, validated
  absolute http(s) or empty) and `Settings.identity_mode`
  (`IDENTITY_MODE`, `anonymous`/`delegated`);
- `CapabilityProvider.tool_capabilities()` reporting `web_rag`/`admin`/
  `sharing`/`attachments` with enabled flags and the RAG status path;
- new `runtime_config` module: `RUNTIME_CONFIG_VERSION = 1`,
  `build_runtime_config()`, and a tolerant `parse_runtime_config()`
  (unknown versions, missing/mistyped fields degrade to compiled defaults);
- `GET /api/config` served per request with `Cache-Control: no-store`;
  `api` added to the SPA reserved paths so it never falls through to HTML;
- `lib/runtime-config.ts` in both frontends mirroring the schema, parser,
  fetcher-with-defaults, and `resolveApiBase` precedence; `tsc --noEmit`
  clean in both apps; TS/Python parity proven ad hoc against
  `tests/fixtures/runtime-config-v1.json` (Node-compiled parser agrees
  with `parse_runtime_config` on fixture, malformed, and future inputs);
- new `runtime-config` guide registered in `docs.py`; configuration env
  table updated.
- wiring (this branch): `hooks/use-runtime-config.ts` loads the manifest
  once per page and derives the effective API base (runtime wins, then
  build-time); `tsc --noEmit` clean.
- capability-gated polling: the thread indexing panel and the source
  widget skip `/tools/web_rag/status` polling when the manifest reports
  `web_rag.enabled: false` (no more 501 spam against the packaged app);
  the admin page shows a disabled-capability notice instead of polling.
- `MyRuntimeProvider` (thread list adapter, per-thread transport, message
  hydration) and all admin calls use the hook's `apiBase`; pre-load
  behavior is byte-identical to the old build-time constant.
- repo hygiene notes: root `.gitignore` `lib/` (a Python rule) also
  covers frontend `lib/`, so new frontend lib files need `git add -f`
  (same as the existing tracked `utils.ts`); repo eslint config crashes
  even on untouched files (pre-existing), `tsc --noEmit` is the working
  gate; full-frontend sources were not prettier-clean, so new hunks keep
  surrounding style instead of whole-file reflows.
- verification: full UI rebuilt + restaged from wired sources; packaged
  app serves `/api/config` (no-store, `web_rag.enabled: false`), `/`,
  and `/full/`; 95 package tests pass; `tsc --noEmit` clean.

## In Progress (stacked on PUIR-08 branch)

### PUIR-09 / #35: Unified static frontend

Branch: `feature/puir-09-unified-frontend` (stacked on
`feature/puir-08-runtime-config`, unmerged PR #39).

- `/full/` is dropped outright per maintainer decision (no redirect shim,
  no second build): one static export served at `/`, preset selected at
  runtime from `/api/config`.
- Scaffold: `application/frontend/frontend/` copied from `frontend-full`
  (the superset), server-only `app/api/chat/route.ts` pruned, `basePath`
  support removed, package renamed to `agent-chat-ui`.

## Tracker

- Tech-debt tracker: #40 (`PUIR-refactor-tech-debt`, P2, parent #22),
  mirrored in `github-issues/PUIR-TD.md` and linked from the recon README.
  Promote items into scoped issues (or fix inline with a checkbox tick)
  rather than letting the list grow silently.

## Test Environment

- Supported verification interpreter used so far: CPython 3.12.3.
- The host's free-threaded CPython 3.14 cannot build the current `orjson`
  dependency; this is an environment/dependency limitation, not a test failure.
- Package-local `uv.lock` files generated during ad hoc runs are intentionally
  removed because this published package does not currently track one.
