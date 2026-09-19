# EPIC_PLAN — Minimal portable app (pip-installable, prebuilt static UI, no Node at install/runtime)

## 0. Epic goal (locked)
Ship the **minimal** flavor as a **local Python wheel** that bundles FastAPI + LangGraph backend
(`application/backend/langgraph-server-minimal`) with a **prebuilt static chat UI**
(`application/frontend/frontend-minimal` → `out/`) served **same-origin from FastAPI on a single port**.

Locked decisions:
- Distribution: **local wheel only** (no PyPI in this epic).
- Backend: **fixed demo agent first** (`demo_agent/get_graph.py`: `get_weather` + `render_graph`). No `create_app(custom_graph)` API in this epic.
- Serving: **same-origin single port** (e.g. `8011` serves `/`, `/assistant`, `/health`). Final artifact must not require `:3000` or `npm/node/pnpm` at install/runtime. Node is allowed **once** at build time to produce `out/`.

End-state check:
```bash
pip install packages/agent-chat-minimal/dist/*.whl  # clean venv, no node
minimal-chat-serve --port 8011                       # or: uvicorn agent_chat_minimal.server:app
# http://localhost:8011/ -> chat UI, same-origin POST /assistant
```

## 1. Issue map + dependency DAG
All issues in `mylonasc/agent-chat-fastapi-langgraph-asisstant-ui`:

| # | Phase | Title | Gate |
|---|-------|-------|------|
| #1 | Phase 0 | Baseline audit & packaging skeleton decision | G0 |
| #2 | Phase 1 | Make frontend-minimal statically exportable | G1 |
| #3 | Phase 2 | Same-origin static serving prototype in FastAPI | G2 |
| #4 | Phase 3 | Repackage as installable local wheel (`src` layout, `web/` bundled) | G3 |
| #5 | Phase 4 | Clean-venv verification, python-only Docker, DX docs | G4 (epic done) |

Dependencies (strictly sequential, no skipping):
```
#1 (G0) -> #2 (G1) -> #3 (G2) -> #4 (G3) -> #5 (G4)
```
- #1 blocks #2,#3,#4,#5. Each issue body lists `Blocked by` / `Blocks`.
- Linkage is duplicated in GitHub issue **comments** (`#issuecomment-...`) so the graph survives even if bodies are edited.
- A phase may not start until its predecessor's gate is checked off in the issue.

Milestone gates:
- **G0:** audit comment posted (export blockers or "none" + wheel-safety verdict + approved package/CLI names). No code.
- **G1:** `pnpm build` → `out/index.html` + `out/_next/`, default API URL relative `/assistant`, `out/` gitignored, `npx serve out` renders.
- **G2:** one `uvicorn ...:8011` serves `/` (HTML), `/_next/*`, `/health`, `/assistant` with no shadowing; missing `web/` degrades to API-only with warning.
- **G3:** `unzip -l dist/*.whl` contains `server.py` + `demo_agent/**` + `web/index.html` + `web/_next/**`; clean venv `pip install` + `import agent_chat_minimal` + `minimal-chat-serve --help` pass.
- **G4:** clean venv **without node** + python-only container prove single-port serving; `pytest` offline passes; README/RUNNING document the flow; follow-ups listed.

Non-goals (do not expand scope): `frontend-full` / full backend, custom-graph injection, PyPI publish, CDN/multi-arch optimization, docling/GPU variants.

## 2. Branch + worktree strategy
- Implementation branch: **`langgraph-ui-portable-app`** (branched from `main` @ `e7f679a`).
- Worktree: `../agent-chat-fastapi-langgraph-asisstant-ui-langgraph-ui-portable-app` (sibling of repo root). `main` checkout stays clean; all epic work happens in the worktree.
  ```bash
  git worktree list
  git -C ../agent-chat-fastapi-langgraph-asisstant-ui-langgraph-ui-portable-app status -sb
  ```
- One phase = one or more small commits on this branch. Reference the issue in every commit (`Phase 1: ... (#2)`). Do not mix phases in a single commit.
- Push regularly: `git push -u origin langgraph-ui-portable-app` (first time), then `git push`. Open **one draft PR** for the epic early (base `main`, head `langgraph-ui-portable-app`, body links #1–#5); mark ready only after G4.
- Never commit `out/`, `web/` build output, `.venv/`, `node_modules/`, or wheels except via `.gitignore` exceptions explicitly documented in Phase 3/4. `EPIC_PLAN.md` (this file) lives on the branch so the workflow travels with the code.
- Cleanup at epic end: after squash/merge, `git worktree remove ../agent-chat-fastapi-langgraph-asisstant-ui-langgraph-ui-portable-app`.

## 3. Phase workflow (repeat for #1..#5)
1. `cd` into the worktree. `git pull --ff-only` if needed.
2. Open the issue, read **Starting point + Tasks + Gate** fully. Check predecessor gate is green.
3. Implement **only** that phase's `IN` scope; leave `OUT` items untouched (note violations in the PR, don't silently include them).
4. Verify with the exact commands in the issue body; paste outputs into the issue as evidence.
5. Commit(s) on `langgraph-ui-portable-app`, push, comment `Gate GX ready for review — <evidence>` on the issue, close **only** when acceptance checkboxes are ticked.
6. Move to next phase. If a prior assumption breaks (e.g. Phase 1 finds an export blocker Phase 0 missed), reopen/update #1 first — don't patch around it downstream.

Suggested per-phase entry points:
- #1: read-only audit (`grep` for SSR APIs, `sys.path` hack, `uv.lock` URL deps). Deliverable = comment, not code.
- #2: `application/frontend/frontend-minimal/next.config.js`, `app/MyRuntimeProvider.tsx`. Last phase allowed to require Node.
- #3: `application/backend/langgraph-server-minimal/server.py` (+ optional `static_mount.py`), `MINIMAL_WEB_DIR` override. No `packages/` dir yet.
- #4: scaffold `packages/agent-chat-minimal/`, `create_app()`/`main()` refactor, hatchling `pyproject.toml`, `pnpm build → cp out → uv build` recipe.
- #5: clean-venv smoke script, `tests/test_serving.py`, python-only `Dockerfile`, README/RUNNING updates.

## 4. Definition of done
Per-phase: all gate checkboxes ticked + evidence pasted in issue + branch pushed with no unrelated diffs.
Epic done (G4): a newcomer with Python only (Node present just for the one-time `out/` build) can go from checkout to working `http://localhost:8011/` chat via `pip install <local wheel>` + `minimal-chat-serve`, proven in both a `python -m venv` without node (`command -v node` fails) and a python-only container; `pytest` passes offline; docs updated; follow-ups (full flavor, custom graph, PyPI) listed, not started.

## 5. Testing + review rules
- Prefer executed evidence over reasoning: `pnpm build`, `curl /health`, `curl /`, `/_next/*` spot-check, `POST /assistant` (503 without key is OK pre-key), `unzip -l`, `pip install` in clean venv, `pytest`, `docker build/run + curl`.
- Keep `application/` dev flow (`uvicorn server:app --port 8011`, `pnpm dev`) working until Phase 4 explicitly decides cutover; don't delete the old backend or compose services mid-epic.
- Review checklist before closing any phase: route ordering (`/assistant`,`/health`,`/docs` before `/` static), no absolute `localhost:8011` leak in default bundle, no `sys.path.append` left in packaged code, wheel contains `web/`, CORS change (if any) justified in writing.
