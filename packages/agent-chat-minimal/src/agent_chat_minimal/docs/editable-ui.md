# Editable UI From the sdist

The wheel ships the prebuilt UI only (HTML/JS/CSS). The source distribution
(sdist) is the editable-UI version: it additionally contains the full
TypeScript/Next.js frontend sources under `ui-src/frontend`, matching the
built bundle in the same release.

## Extract And Rebuild

```bash
pip download --no-binary :all: agent-chat-fastapi-langgraph-assistant-ui
tar -xzf agent-chat-fastapi-langgraph-assistant-ui-*.tar.gz
cd agent-chat-fastapi-langgraph-assistant-ui-*/ui-src/frontend
pnpm install --frozen-lockfile
pnpm build
```

Node 20+ and pnpm 10+ are required for the rebuild (same pins as the
repository). No Python environment is needed for this step.

## Serve the Edited UI

Point the packaged server at the rebuilt static export; the server keeps
serving the API and mounts the override instead of the bundled UI:

```bash
MINIMAL_WEB_DIR=/path/to/ui-src/frontend/out minimal-chat-serve --port 8011
```

`MINIMAL_WEB_DIR` (and `FULL_WEB_DIR` for the `/full` mount) accept any
directory containing a servable static UI bundle (`index.html`). For split
development against a live dev server instead, see the Compose stacks in the
repository's Docker Compose guide.

## Notes And Limits

- The wheel intentionally omits `ui-src/` to stay runtime-only; download the
  sdist when sources are needed.
- `ui-src/` excludes install/build outputs (`node_modules`, `.next`, `out`),
  so a fresh `pnpm install` is always the first step.
- The staged sources and the prebuilt `web/` bundle come from the same
  `scripts/stage_ui*.sh` run during the release build, so they match per
  version. Rebuilding after edits intentionally diverges from the bundle.
