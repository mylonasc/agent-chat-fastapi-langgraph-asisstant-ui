# Frontend e2e suites by backend target (#64)

Two backends, two suite kinds. Tags (`@packaged`, `@full-backend` in test
titles) and per-suite configs enforce the split; `--grep` also works.

## Packaged app (`@packaged`, self-contained)

Run against the wheel's FastAPI + bundled UI via `helpers/fake_backend.py`
(deterministic echo agent, no network, no credentials). Each suite spins its
own server through the config's `webServer` entry.

| Suite | Config | What it covers |
|---|---|---|
| `thread-sync.spec.ts` | `e2e/thread-sync.config.ts` | Turn ordering, feedback + thread switching across reload |
| `backend-base.spec.ts` | `e2e/backend-base.config.ts` | Same-origin backend I/O, titles, archive, starter page |
| `error-surfacing.spec.ts` | `e2e/error-debug.config.ts` / `e2e/error-prod.config.ts` | Backend-error surfacing per `server_mode` |

```bash
cd application/frontend/frontend
pnpm install
pnpm exec playwright install --with-deps chromium
pnpm build  # fake_backend serves out/
pnpm playwright test -c e2e/thread-sync.config.ts
pnpm playwright test -c e2e/backend-base.config.ts
pnpm playwright test -c e2e/error-debug.config.ts
pnpm playwright test -c e2e/error-prod.config.ts
```

These suites run in CI on every artifact build
(`.github/workflows/artifact-workflow.yml`, `e2e-packaged` job).

## Full backend (`@full-backend`, live stack only)

`tool-availability.spec.ts` and `generative-ui-rag.spec.ts` (identical copies
in `frontend/e2e/` and `frontend-full/e2e/`) assume the split Compose stack:
full backend on `:8010` with `OPENAI_API_KEY`/`SERPER_API_KEY`, plus tool
administration credentials via `FULL_ADMIN_TOKEN` (#36). Without reachable
admin-authorized tool APIs they skip; they never run against the packaged
app (the default `playwright.config.ts` ignores them).

```bash
# from either frontend dir, with the compose stack up:
FULL_ADMIN_TOKEN=... API_BASE_URL=http://localhost:8010 \
  pnpm playwright test -c e2e/full-backend.config.ts   # frontend/
pnpm test:e2e                                          # frontend-full/ (same suites)
```

## Out of scope

`tests/ui/` is a separate DOM-inspection harness against the Compose UIs,
not a backend-target suite split; see `tests/ui/README.md`.
