Tracker: #40 (https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/40)

Parent: #22

Priority: P2

Collects TODOs, discovered gaps, and potential improvements found during
the UI-refactor initiative that are not covered (or not yet scheduled) by
a numbered PUIR issue. The live checklist lives on the issue; the groups
below mirror it at creation time.

## Frontend toolchain

- Root `.gitignore` `lib/` (Python rule) forces `git add -f` for frontend
  lib files; scope the rule.
- Repo eslint config crashes on every file (pre-existing); repair/replace.
- Full-frontend sources are not prettier-formatted; decide normalization.
- Frontend e2e specs assume full-backend `/tools/*`; gate per backend.

## Identity and session UX

- Full UI hardcodes `user_id=default_user`, never sends the subject
  header (belongs with PUIR-10).
- Minimal UI has no runtime `api_base` consumption (PUIR-09).
- Message checkpointer fallback bypasses ownership for unknown sessions.
- Admin controls stay clickable when RAG is disabled (501 JSON, no crash).

## Persistence and composition

- No transcript growth/trim policy (legacy had 500/200 caps).
- Service delete is multi-repository, not atomic (documented).
- Composition can silently mix memory checkpointer with SQLite deleter.
- No lifespan ownership for SQLite/checkpoint adapters.

## Docs and process

- `RUNNING.md` deferred-follow-ups paragraph is stale (shipped in 0.4.0).
- Recon handoff on `main` still describes PUIR-07 as pending.
- Smoke test does not assert `/api/config`.
- Publish flow is manual; consider checklist/automation (PUIR-14).
